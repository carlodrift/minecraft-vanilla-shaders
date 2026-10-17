import net.fabricmc.api.ClientModInitializer;

import java.nio.file.Path;

/**
 * The test agent as a Fabric mod, for runs with mods (launch.py --fabric). Under Fabric the game's classes
 * are loaded by Fabric's class loader, which a -javaagent doesn't share, so the script runs from here.
 * The script path comes from the shadertest.script system property.
 */
public class ShaderTestFabric implements ClientModInitializer {
    @Override
    public void onInitializeClient() {
        String script = System.getProperty("shadertest.script");
        if (script != null) {
            Thread t = new Thread(() -> ShaderTestAgent.run(Path.of(script)), "shader-test-agent");
            t.setDaemon(true);
            t.start();
        }
    }
}
