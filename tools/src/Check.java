import com.google.gson.JsonParser;
import com.mojang.renderpearl.api.pipeline.BindGroupLayout;
import com.mojang.renderpearl.api.pipeline.RenderPipeline;
import com.mojang.renderpearl.api.pipeline.ShaderType;
import com.mojang.renderpearl.api.pipeline.UniformType;
import com.mojang.renderpearl.api.vertex.VertexFormat;
import com.mojang.renderpearl.api.vertex.VertexFormatElement;
import com.mojang.renderpearl.backend.api.SpvModule;
import com.mojang.renderpearl.frontend.shaders.SPIRVModule;
import com.mojang.renderpearl.frontend.shaders.SpvUtil;
import com.mojang.serialization.JsonOps;
import net.minecraft.SharedConstants;
import net.minecraft.client.renderer.PostChain;
import net.minecraft.client.renderer.PostChainConfig;
import net.minecraft.client.renderer.RenderPipelines;
import net.minecraft.resources.Identifier;
import org.lwjgl.system.MemoryUtil;
import org.lwjgl.util.shaderc.Shaderc;
import org.lwjgl.util.shaderc.ShadercIncludeResolve;
import org.lwjgl.util.shaderc.ShadercIncludeResult;
import org.lwjgl.util.shaderc.ShadercIncludeResultRelease;

import java.io.IOException;
import java.io.InputStream;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;
import java.util.stream.Stream;

/**
 * Checks a resource pack's shaders the way Minecraft 26.3 loads them, without launching the game.
 *
 * 1. Compile: every shader variant (shader + the defines of each pipeline using it) is compiled with
 *    shaderc using the game's options (Vulkan 1.2 target, auto-bound uniforms, no optimisation,
 *    includes resolved by identifier in shaders/include/), once per combination of the three
 *    device-dependent RENDERPEARL_* macros.
 * 2. Link: every pipeline is then validated like the game does after compiling: vertex attributes
 *    against the pipeline's vertex format (by name), vertex outputs against fragment inputs (by
 *    location), uniform blocks and samplers against the pipeline's uniforms (by name), push constants.
 *
 * Usage: Check [resource-pack-dir]   (without a pack, checks vanilla only)
 */
public class Check {
    static final String[] DEVICE_MACROS = {
        "RENDERPEARL_DEPTH_IS_ZERO_TO_ONE",
        "RENDERPEARL_EXPLICIT_DEPTH_INVARIANCE",
        "RENDERPEARL_INSTANCE_INDEX_INCLUDES_BASE_INSTANCE",
    };
    static final int PROFILES = 1 << DEVICE_MACROS.length;
    static final int SHADERC_TARGET_ENV_VULKAN = 0;
    static final int SHADERC_ENV_VERSION_VULKAN_1_2 = (1 << 22) | (2 << 12);
    // SPIR-V decorations and SPIRV-Cross base types used by the link checks.
    static final int DECORATION_FLAT = 14;
    static final int DECORATION_COMPONENT = 31;
    static final int BASETYPE_INT32 = 7;
    static final int BASETYPE_UINT32 = 8;
    static final int BASETYPE_FP32 = 13;

    record Variant(Identifier shader, ShaderType type, Map<String, String> values, Set<String> flags) {
        Identifier file() {
            // assets/<ns>/shaders/<path>.vsh|.fsh, as ShaderManager loads them.
            return shader.withPath(path -> "shaders/" + path + (type == ShaderType.FRAGMENT ? ".fsh" : ".vsh"));
        }
    }

    /** Result of compiling one variant under one device profile: SPIR-V or an error. */
    record Compiled(SpvModule module, String error, boolean fromPack) {}

    static Path pack;
    static final Map<Variant, Compiled[]> compiled = new HashMap<>();
    /** Problem message -> device profiles -> pipelines, so identical errors are reported once. */
    static final Map<String, Map<String, Set<String>>> problems = new TreeMap<>();

    public static void main(String[] args) throws IOException {
        SharedConstants.tryDetectVersion();
        pack = args.length > 0 ? Path.of(args[0]) : null;
        if (pack != null && !Files.isDirectory(pack.resolve("assets"))) {
            System.err.println("Not a resource pack directory (no assets/): " + pack);
            System.exit(2);
        }

        List<RenderPipeline> pipelines = new ArrayList<>(RenderPipelines.requiredPipelines());
        pipelines.addAll(RenderPipelines.optionalPipelines());
        pipelines.addAll(postPipelines());

        long compiler = Shaderc.shaderc_compiler_initialize();
        int checkedPipelines = 0;
        try {
            for (RenderPipeline pipeline : pipelines) {
                boolean involvesPack = false;
                for (int profile = 0; profile < PROFILES; profile++) {
                    Map<ShaderType, Compiled> stages = new LinkedHashMap<>();
                    for (Map.Entry<ShaderType, Identifier> shader : pipeline.getShaders().entrySet()) {
                        Variant v = new Variant(shader.getValue(), shader.getKey(),
                            new TreeMap<>(pipeline.getShaderDefines().values()), new TreeSet<>(pipeline.getShaderDefines().flags()));
                        Compiled c = compiled.computeIfAbsent(v, k -> new Compiled[PROFILES])[profile];
                        if (c == null) {
                            c = compile(compiler, v, profile);
                            compiled.get(v)[profile] = c;
                        }
                        stages.put(shader.getKey(), c);
                        involvesPack |= c.fromPack();
                    }
                    if (pack != null && !involvesPack) {
                        break;
                    }
                    String location = pipeline.getLocation().toString();
                    boolean compileFailed = false;
                    for (Compiled c : stages.values()) {
                        if (c.error() != null) {
                            problem(c.error(), profile, location);
                            compileFailed = true;
                        }
                    }
                    if (!compileFailed) {
                        String linkError = link(pipeline, stages);
                        if (linkError != null) {
                            problem(linkError, profile, location);
                        }
                    }
                }
                if (pack == null || involvesPack) {
                    checkedPipelines++;
                }
            }
        } finally {
            Shaderc.shaderc_compiler_release(compiler);
        }

        problems.forEach((message, byProfiles) -> byProfiles.forEach((profiles, locations) -> {
            System.out.println("FAIL");
            message.lines().forEach(l -> System.out.println("  | " + l));
            System.out.println("  pipelines: " + summarize(new ArrayList<>(locations)));
            System.out.println("  device:    " + profiles);
        }));
        long variantsFromPack = compiled.values().stream().filter(cs -> cs[0] != null && cs[0].fromPack()).count();
        System.out.printf("%n%d pipelines checked, %d shader variants (%d from the pack), %d problems%n",
            checkedPipelines, compiled.size(), variantsFromPack, problems.values().stream().mapToInt(Map::size).sum());
        System.exit(problems.isEmpty() ? 0 : 1);
    }

    static void problem(String message, int profile, String pipeline) {
        problems.computeIfAbsent(message, m -> new TreeMap<>());
        // Merge the profile into the entry that already lists this pipeline, keyed by the profile set.
        Map<String, Set<String>> byProfiles = problems.get(message);
        String previous = null;
        for (Map.Entry<String, Set<String>> e : byProfiles.entrySet()) {
            if (e.getValue().contains(pipeline)) {
                previous = e.getKey();
            }
        }
        if (previous != null) {
            byProfiles.get(previous).remove(pipeline);
            if (byProfiles.get(previous).isEmpty()) {
                byProfiles.remove(previous);
            }
        }
        String profiles = previous == null ? profileName(profile) : previous + " | " + profileName(profile);
        if (profiles.split(" \\| ").length == PROFILES) {
            profiles = "all";
        }
        byProfiles.computeIfAbsent(profiles, k -> new TreeSet<>()).add(pipeline);
    }

    /** Post-effect pipelines, built like net.minecraft.client.renderer.PostChain does. */
    static List<RenderPipeline> postPipelines() throws IOException {
        Map<String, String> configs = new TreeMap<>();
        for (String name : List.of("blur", "creeper", "entity_outline", "invert", "spider")) {
            configs.put("minecraft:" + name, read(Identifier.withDefaultNamespace("post_effect/" + name + ".json")));
        }
        if (pack != null) {
            try (Stream<Path> files = Files.walk(pack.resolve("assets"))) {
                for (Path f : files.filter(f -> f.toString().endsWith(".json")).toList()) {
                    Path rel = pack.resolve("assets").relativize(f);
                    if (rel.getNameCount() >= 3 && rel.getName(1).toString().equals("post_effect")) {
                        String path = rel.subpath(2, rel.getNameCount()).toString().replace('\\', '/');
                        configs.put(rel.getName(0) + ":" + path.substring(0, path.length() - ".json".length()), Files.readString(f));
                    }
                }
            }
        }
        List<RenderPipeline> result = new ArrayList<>();
        configs.forEach((id, json) -> {
            if (json == null) {
                return;
            }
            PostChainConfig config = PostChainConfig.CODEC.parse(JsonOps.INSTANCE, JsonParser.parseString(json)).getOrThrow();
            // Post effects run as end_of_frame or through /posteffect may only use minecraft:main among the
            // game's targets (minecraft:entity_outline is the only vanilla chain allowed more).
            Set<Identifier> external = new TreeSet<>(PostChain.getReferencedExternalTargets(config));
            external.remove(PostChain.MAIN_TARGET_ID);
            if (!external.isEmpty() && !id.equals("minecraft:entity_outline")) {
                problems.computeIfAbsent("post effect " + id + " uses targets a post effect cannot access: " + external, m -> new TreeMap<>())
                    .put("all", new TreeSet<>(Set.of("post_effect/" + id.replace(":", "/"))));
            }
            for (int i = 0; i < config.passes().size(); i++) {
                PostChainConfig.Pass pass = config.passes().get(i);
                BindGroupLayout.Builder uniforms = BindGroupLayout.builder();
                for (PostChainConfig.Input input : pass.inputs()) {
                    uniforms.withUniform(input.samplerName() + "Sampler", UniformType.COMBINED_IMAGE_SAMPLER);
                }
                uniforms.withUniform("SamplerInfo", UniformType.UNIFORM_BUFFER);
                for (String block : pass.uniforms().keySet()) {
                    uniforms.withUniform(block, UniformType.UNIFORM_BUFFER);
                }
                result.add(RenderPipeline.builder(RenderPipelines.POST_PROCESSING_SNIPPET)
                    .withFragmentShader(pass.fragmentShaderId())
                    .withVertexShader(pass.vertexShaderId())
                    .withBindGroupLayout(uniforms.build())
                    .withLocation("post_effect/" + id.replace(":", "/") + "/" + i)
                    .build());
            }
        });
        return result;
    }

    static Compiled compile(long compiler, Variant v, int profile) {
        String source = read(v.file());
        boolean fromPack = isInPack(v.file());
        if (source == null) {
            return new Compiled(null, "shader source not found: " + v.file(), fromPack);
        }
        long options = Shaderc.shaderc_compile_options_initialize();
        List<Long> results = new ArrayList<>();
        boolean[] includesFromPack = {false};
        ShadercIncludeResolve resolver = ShadercIncludeResolve.create((userData, requested, type, requesting, depth) -> {
            Identifier id = Identifier.tryParse(MemoryUtil.memASCII(requested));
            String content = null;
            String error = "malformed id";
            if (id != null) {
                Identifier location = id.withPrefix("shaders/include/");
                content = read(location);
                error = "not found";
                includesFromPack[0] |= content != null && isInPack(location);
            }
            ShadercIncludeResult result = ShadercIncludeResult.calloc();
            result.source_name(MemoryUtil.memUTF8(content == null ? "" : id.toString(), false));
            result.content(MemoryUtil.memUTF8(content == null ? error : content, false));
            results.add(result.address());
            return result.address();
        });
        ShadercIncludeResultRelease release = ShadercIncludeResultRelease.create((userData, result) -> {});
        ByteBuffer src = MemoryUtil.memUTF8(source, false);
        ByteBuffer file = MemoryUtil.memUTF8(v.file().toString());
        ByteBuffer entry = MemoryUtil.memUTF8("main");
        try {
            Shaderc.shaderc_compile_options_set_target_env(options, SHADERC_TARGET_ENV_VULKAN, SHADERC_ENV_VERSION_VULKAN_1_2);
            Shaderc.shaderc_compile_options_set_auto_bind_uniforms(options, true);
            Shaderc.shaderc_compile_options_set_preserve_bindings(options, false);
            Shaderc.shaderc_compile_options_set_generate_debug_info(options);
            Shaderc.shaderc_compile_options_set_optimization_level(options, 0);
            for (int i = 0; i < DEVICE_MACROS.length; i++) {
                if ((profile & (1 << i)) != 0) {
                    Shaderc.shaderc_compile_options_add_macro_definition(options, DEVICE_MACROS[i], "");
                }
            }
            v.values().forEach((k, val) -> Shaderc.shaderc_compile_options_add_macro_definition(options, k, val));
            v.flags().forEach(flag -> Shaderc.shaderc_compile_options_add_macro_definition(options, flag, ""));
            Shaderc.shaderc_compile_options_set_include_callbacks(options, resolver, release, 0L);
            long result = Shaderc.shaderc_compile_into_spv(compiler, src, v.type() == ShaderType.FRAGMENT ? 1 : 0, file, entry, options);
            try {
                fromPack |= includesFromPack[0];
                if (Shaderc.shaderc_result_get_compilation_status(result) != 0) {
                    return new Compiled(null, Shaderc.shaderc_result_get_error_message(result).strip(), fromPack);
                }
                ByteBuffer spirv = Shaderc.shaderc_result_get_bytes(result);
                ByteBuffer copy = MemoryUtil.memCalloc(spirv.remaining());
                MemoryUtil.memCopy(spirv, copy);
                return new Compiled(spirvModule(v.file().toString(), copy, v.type()), null, fromPack);
            } finally {
                Shaderc.shaderc_result_release(result);
            }
        } finally {
            Shaderc.shaderc_compile_options_release(options);
            resolver.free();
            release.free();
            for (long r : results) {
                MemoryUtil.nmemFree(MemoryUtil.memGetAddress(r + ShadercIncludeResult.SOURCE_NAME));
                MemoryUtil.nmemFree(MemoryUtil.memGetAddress(r + ShadercIncludeResult.CONTENT));
                MemoryUtil.nmemFree(r);
            }
            MemoryUtil.memFree(src);
            MemoryUtil.memFree(file);
            MemoryUtil.memFree(entry);
        }
    }

    /** The checks the game runs on a pipeline once both stages compiled; returns the first problem. */
    static String link(RenderPipeline pipeline, Map<ShaderType, Compiled> stages) {
        try {
            String vsh = pipeline.getShaders().getOrDefault(ShaderType.VERTEX, Identifier.withDefaultNamespace("")).toString();
            String fsh = pipeline.getShaders().get(ShaderType.FRAGMENT).toString();

            Map<Integer, String[]> vertexOutputs = Map.of();
            if (stages.containsKey(ShaderType.VERTEX)) {
                SpvModule.Reflection vertex = stages.get(ShaderType.VERTEX).module().reflect();
                // Vertex attributes are matched to the pipeline's vertex format by name.
                Map<Integer, VertexFormatElement> attributes = new HashMap<>();
                for (VertexFormat format : pipeline.getVertexFormatBindings()) {
                    if (format == null) {
                        continue;
                    }
                    String previousName = null;
                    int previousLocation = 0;
                    for (VertexFormatElement element : format.getElements()) {
                        for (SpvModule.Reflection.InterfaceVariable input : vertex.inputs()) {
                            if (input.name().equals(element.name())) {
                                int location = element.name().equals(previousName) ? previousLocation + 1 : input.location();
                                attributes.put(location, element);
                                previousName = element.name();
                                previousLocation = location;
                            }
                        }
                    }
                }
                for (SpvModule.Reflection.InterfaceVariable input : vertex.inputs()) {
                    if (input.hasDecoration(DECORATION_COMPONENT)) {
                        return vsh + ": vertex attribute " + input.name() + " has a component decoration, not permitted";
                    }
                    VertexFormatElement element = attributes.get(input.location());
                    if (element == null) {
                        return vsh + ": vertex attribute " + input.name() + " is not in the pipeline's vertex format";
                    }
                    int expected = switch (element.format().componentType()) {
                        case UINT_8, UINT_16, UINT_32 -> BASETYPE_UINT32;
                        case SINT_8, SINT_16, SINT_32 -> BASETYPE_INT32;
                        default -> BASETYPE_FP32;
                    };
                    if (expected != input.type().baseType()) {
                        return vsh + ": vertex attribute " + input.name() + " must be " + SpvUtil.baseTypeString(expected)
                            + "-based, got " + SpvUtil.baseTypeString(input.type().baseType());
                    }
                    if (input.type().vectorSize() > element.format().componentCount()) {
                        return vsh + ": vertex attribute " + input.name() + " has " + input.type().vectorSize()
                            + " components, the vertex format only provides " + element.format().componentCount();
                    }
                }
                vertexOutputs = slots(vertex.outputs());
            }

            // Fragment inputs are matched to vertex outputs by location only; names are ignored.
            for (Map.Entry<Integer, String[]> in : slots(stages.get(ShaderType.FRAGMENT).module().reflect().inputs()).entrySet()) {
                String[] out = vertexOutputs.get(in.getKey());
                if (out == null) {
                    return fsh + ": input at location " + in.getKey() + " has no matching output in " + vsh;
                }
                if (!out[0].equals(in.getValue()[0])) {
                    return vsh + " -> " + fsh + ": type mismatch at location " + in.getKey() + " (" + out[0] + " vs " + in.getValue()[0] + ")";
                }
            }

            // Every uniform block and sampler a shader declares must be provided by the pipeline, by name.
            Map<String, UniformType> provided = new HashMap<>();
            for (BindGroupLayout.UniformDescription u : BindGroupLayout.flattenUniforms(pipeline.getBindGroupLayouts())) {
                provided.put(u.name(), u.type());
            }
            for (Map.Entry<ShaderType, Compiled> stage : stages.entrySet()) {
                String name = pipeline.getShaders().get(stage.getKey()).toString();
                SpvModule.Reflection reflection = stage.getValue().module().reflect();
                for (SpvModule.Reflection.Descriptor d : reflection.descriptors()) {
                    UniformType type = provided.get(d.name());
                    if (type == null) {
                        return name + ": uniform " + d.name() + " is not provided by this pipeline (available: "
                            + String.join(", ", new TreeSet<>(provided.keySet())) + ")";
                    }
                    if (d.resourceType() != SpvUtil.resourceType(type)) {
                        return name + ": uniform " + d.name() + " must be a " + type;
                    }
                    int dims = d.type().dimensions();
                    if (dims == 0 || dims == 2) {
                        return name + ": uniform " + d.name() + ": 1D and 3D textures are not supported";
                    }
                }
                if (reflection.pushConstants().size() > 1) {
                    return name + ": at most one push_constant block";
                }
                if (!reflection.pushConstants().isEmpty() && reflection.pushConstants().getFirst().size() > pipeline.pushConstantSize()) {
                    return name + ": push constant block larger than the pipeline allows (" + pipeline.pushConstantSize() + " bytes)";
                }
            }
            return null;
        } catch (Exception e) {
            return "reflection failed: " + e.getMessage();
        }
    }

    /** location -> {type description}; arrays take one slot per element. */
    static Map<Integer, String[]> slots(List<SpvModule.Reflection.InterfaceVariable> variables) throws Exception {
        Map<Integer, String[]> slots = new HashMap<>();
        for (SpvModule.Reflection.InterfaceVariable v : variables) {
            if (v.hasDecoration(DECORATION_COMPONENT)) {
                throw new Exception(v.name() + " has a component decoration, not permitted");
            }
            SpvModule.Reflection.Type t = v.type();
            String type = SpvUtil.baseTypeString(t.baseType()) + "x" + t.vectorSize() + (v.hasDecoration(DECORATION_FLAT) ? " flat" : "");
            int size = 1;
            for (int i = 0; i < t.arrayDimensions(); i++) {
                size *= t.arrayLength(i);
            }
            for (int i = 0; i < size; i++) {
                slots.put(v.location() + i, new String[]{type});
            }
        }
        return slots;
    }

    /** The game's SPIR-V reflection wrapper: (spv, type) in 26.3, (name, spv, type, entry point) in 26.4. */
    static SpvModule spirvModule(String name, ByteBuffer spv, ShaderType type) {
        try {
            for (java.lang.reflect.Constructor<?> c : SPIRVModule.class.getConstructors()) {
                if (c.getParameterCount() == 2) {
                    return (SpvModule) c.newInstance(spv, type);
                }
                if (c.getParameterCount() == 4) {
                    return (SpvModule) c.newInstance(name, spv, type, "main");
                }
            }
        } catch (ReflectiveOperationException e) {
            throw new RuntimeException(e);
        }
        throw new IllegalStateException("unknown SPIRVModule constructor");
    }

    /** Reads assets/<namespace>/<path>, from the pack first, then from the game jar. */
    static String read(Identifier location) {
        try {
            if (isInPack(location)) {
                return Files.readString(packPath(location));
            }
            try (InputStream in = Check.class.getClassLoader().getResourceAsStream("assets/" + location.getNamespace() + "/" + location.getPath())) {
                return in == null ? null : new String(in.readAllBytes(), StandardCharsets.UTF_8);
            }
        } catch (IOException e) {
            throw new RuntimeException(e);
        }
    }

    static boolean isInPack(Identifier location) {
        return pack != null && Files.isRegularFile(packPath(location));
    }

    static Path packPath(Identifier location) {
        return pack.resolve("assets").resolve(location.getNamespace()).resolve(location.getPath());
    }

    static String profileName(int profile) {
        List<String> on = new ArrayList<>();
        for (int i = 0; i < DEVICE_MACROS.length; i++) {
            if ((profile & (1 << i)) != 0) {
                on.add(DEVICE_MACROS[i].substring("RENDERPEARL_".length()));
            }
        }
        return on.isEmpty() ? "(none)" : String.join("+", on);
    }

    static String summarize(List<String> items) {
        return items.size() > 5 ? String.join(", ", items.subList(0, 5)) + ", … (" + items.size() + " total)" : String.join(", ", items);
    }
}
