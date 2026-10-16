import com.mojang.renderpearl.api.pipeline.BindGroupLayout;
import com.mojang.renderpearl.api.pipeline.RenderPipeline;
import com.mojang.renderpearl.api.vertex.VertexFormat;
import net.minecraft.client.renderer.RenderPipelines;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.TreeSet;

/** Dumps every registered render pipeline of the running game version as JSON lines. */
public class DumpPipelines {
    public static void main(String[] args) {
        net.minecraft.SharedConstants.tryDetectVersion();
        List<RenderPipeline> all = new ArrayList<>();
        all.addAll(RenderPipelines.requiredPipelines());
        all.addAll(RenderPipelines.optionalPipelines());
        all.sort(Comparator.comparing(p -> p.getLocation().toString()));
        for (RenderPipeline p : all) {
            StringBuilder sb = new StringBuilder("{");
            sb.append("\"location\":").append(q(p.getLocation().toString()));
            sb.append(",\"optional\":").append(RenderPipelines.optionalPipelines().contains(p));
            p.getShaders().forEach((type, id) -> sb.append(",\"").append(type.name().toLowerCase()).append("\":").append(q(id.toString())));
            Map<String, String> values = new TreeMap<>(p.getShaderDefines().values());
            sb.append(",\"defines\":{");
            sb.append(String.join(",", values.entrySet().stream().map(e -> q(e.getKey()) + ":" + q(e.getValue())).toList()));
            sb.append("},\"flags\":[");
            sb.append(String.join(",", new TreeSet<>(p.getShaderDefines().flags()).stream().map(DumpPipelines::q).toList()));
            sb.append("],\"uniforms\":[");
            // Sorted: the game's own order is not stable from one run to the next.
            sb.append(String.join(",", BindGroupLayout.flattenUniforms(p.getBindGroupLayouts()).stream()
                .sorted(Comparator.comparing(BindGroupLayout.UniformDescription::name))
                .map(u -> "{\"name\":" + q(u.name()) + ",\"type\":" + q(u.type().name()) + "}").toList()));
            sb.append("],\"vertex_formats\":[");
            List<String> formats = new ArrayList<>();
            List<VertexFormat> bindings = p.getVertexFormatBindings();
            for (int i = 0; i < bindings.size(); i++) {
                VertexFormat f = bindings.get(i);
                if (f == null) {
                    continue;
                }
                formats.add("{\"binding\":" + i + ",\"step_rate\":" + f.getStepRate() + ",\"attributes\":["
                    + String.join(",", f.getElements().stream()
                        .map(e -> "{\"name\":" + q(e.name()) + ",\"format\":" + q(e.format().name()) + "}").toList())
                    + "]}");
            }
            sb.append(String.join(",", formats));
            sb.append("],\"topology\":").append(q(p.getPrimitiveTopology().name()));
            sb.append(",\"cull\":").append(p.isCull());
            sb.append(",\"polygon_mode\":").append(q(p.getPolygonMode().name()));
            sb.append(",\"depth_stencil\":").append(q(String.valueOf(p.getDepthStencilState())));
            sb.append(",\"color_targets\":").append(q(String.valueOf(p.getColorTargetStates())));
            sb.append("}");
            System.out.println(sb);
        }
    }

    static String q(String s) {
        return "\"" + s.replace("\\", "\\\\").replace("\"", "\\\"") + "\"";
    }
}
