import com.mojang.renderpearl.api.pipeline.RenderPipeline;
import net.minecraft.client.renderer.RenderPipelines;

import java.lang.reflect.Array;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * The game's render pipelines, and how a post pass starts, across the versions the tools support. The two
 * APIs differ, so this goes through reflection:
 *
 *  - up to 26.4-snapshot-4, RenderPipelines lists them: requiredPipelines() and optionalPipelines(), and post
 *    passes start from RenderPipelines.POST_PROCESSING_SNIPPET;
 *  - from 26.4-snapshot-5, most pipelines are built from parameters, for the options in use:
 *    staticPipelinesToPrecompile() and dynamicPipelinesToPrecompile(context), and post passes start from
 *    GLOBALS_SNIPPET with triangles and the default color target (PostChain.createPass);
 *  - from 26.4-snapshot-6, those lists hold PipelineCache.Key(pipeline, subpass): a pipeline appears once per
 *    render subpass it is compiled for, and the shaders are the same for each.
 */
final class GamePipelines {
    record Entry(RenderPipeline pipeline, boolean optional) {}

    private GamePipelines() {}

    /** Every pipeline, once each. Optional: only compiled for some options or devices. */
    static List<Entry> all() {
        try {
            Method required = RenderPipelines.class.getMethod("requiredPipelines");
            Method optional = RenderPipelines.class.getMethod("optionalPipelines");
            List<Entry> result = new ArrayList<>();
            for (Object p : (List<?>) required.invoke(null)) {
                result.add(new Entry((RenderPipeline) p, false));
            }
            for (Object p : (List<?>) optional.invoke(null)) {
                result.add(new Entry((RenderPipeline) p, true));
            }
            return result;
        } catch (NoSuchMethodException e) {
            return fromParameters();
        } catch (ReflectiveOperationException e) {
            throw new IllegalStateException(e);
        }
    }

    /**
     * 26.4-snapshot-5 and later: the static pipelines, plus the dynamic ones for every combination of the
     * options that change them (Improved Transparency, multidraw terrain, fancy or fast clouds). Optional:
     * absent with the defaults (no Improved Transparency, no multidraw, fancy clouds).
     */
    private static List<Entry> fromParameters() {
        try {
            Class<?> contextClass = Class.forName("net.minecraft.client.renderer.ShaderManager$PipelineCompilationContext");
            Class<?> optionsClass = Class.forName("net.minecraft.client.renderer.state.OptionsRenderState");
            Method dynamic = RenderPipelines.class.getMethod("dynamicPipelinesToPrecompile", contextClass);
            Map<String, Entry> byLocation = new LinkedHashMap<>();
            for (Object p : (List<?>) RenderPipelines.class.getMethod("staticPipelinesToPrecompile").invoke(null)) {
                byLocation.putIfAbsent(location(p), new Entry(pipeline(p), false));
            }
            Set<String> defaults = null;
            for (boolean improvedTransparency : new boolean[] {false, true}) {
                for (boolean multidraw : new boolean[] {false, true}) {
                    for (String clouds : new String[] {"FANCY", "FAST"}) {
                        Object options = optionsClass.getConstructor().newInstance();
                        optionsClass.getField("improvedTransparency").setBoolean(options, improvedTransparency);
                        var cloudStatus = optionsClass.getField("cloudStatus");
                        cloudStatus.set(options, constant(cloudStatus.getType(), clouds));
                        Object context = contextClass.getConstructors()[0].newInstance(options, multidraw);
                        List<?> pipelines = (List<?>) dynamic.invoke(null, context);
                        if (defaults == null) {
                            defaults = pipelines.stream().map(GamePipelines::location).collect(Collectors.toSet());
                        }
                        for (Object p : pipelines) {
                            byLocation.putIfAbsent(location(p), new Entry(pipeline(p), !defaults.contains(location(p))));
                        }
                    }
                }
            }
            return new ArrayList<>(byLocation.values());
        } catch (ReflectiveOperationException e) {
            throw new IllegalStateException("cannot list this version's render pipelines", e);
        }
    }

    /** A builder for a post pass, before its shaders, uniforms and location. */
    static RenderPipeline.Builder postPassBuilder() {
        try {
            try {
                return builder(RenderPipelines.class.getField("POST_PROCESSING_SNIPPET").get(null));
            } catch (NoSuchFieldException e) {
                Object b = builder(RenderPipelines.class.getField("GLOBALS_SNIPPET").get(null));
                b = withConstant(b, "withPrimitiveTopology", "TRIANGLES");
                b = withConstant(b, "withColorTargetState", "DEFAULT");
                return (RenderPipeline.Builder) b;
            }
        } catch (ReflectiveOperationException e) {
            throw new IllegalStateException("cannot build a post pass for this version", e);
        }
    }

    private static String location(Object pipelineOrKey) {
        return pipeline(pipelineOrKey).getLocation().toString();
    }

    /** The pipeline itself, or the one a PipelineCache.Key (26.4-snapshot-6) refers to. */
    private static RenderPipeline pipeline(Object pipelineOrKey) {
        if (pipelineOrKey instanceof RenderPipeline p) {
            return p;
        }
        try {
            return (RenderPipeline) pipelineOrKey.getClass().getMethod("pipeline").invoke(pipelineOrKey);
        } catch (ReflectiveOperationException e) {
            throw new IllegalStateException("unknown pipeline list element: " + pipelineOrKey.getClass(), e);
        }
    }

    private static RenderPipeline.Builder builder(Object snippet) throws ReflectiveOperationException {
        for (Method m : RenderPipeline.class.getMethods()) {
            if (m.getName().equals("builder") && m.getParameterCount() == 1 && m.getParameterTypes()[0].isArray()) {
                Object snippets = Array.newInstance(m.getParameterTypes()[0].getComponentType(), 1);
                Array.set(snippets, 0, snippet);
                return (RenderPipeline.Builder) m.invoke(null, snippets);
            }
        }
        throw new NoSuchMethodException("RenderPipeline.builder(Snippet...)");
    }

    /** builder.name(X), where X is the enum constant or the static field of that name of the parameter's type. */
    private static Object withConstant(Object builder, String name, String constant) throws ReflectiveOperationException {
        for (Method m : builder.getClass().getMethods()) {
            if (m.getName().equals(name) && m.getParameterCount() == 1) {
                return m.invoke(builder, constant(m.getParameterTypes()[0], constant));
            }
        }
        throw new NoSuchMethodException(name);
    }

    @SuppressWarnings({"unchecked", "rawtypes"})
    private static Object constant(Class<?> type, String name) throws ReflectiveOperationException {
        return type.isEnum() ? Enum.valueOf((Class<Enum>) type, name) : type.getField(name).get(null);
    }
}
