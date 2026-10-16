import net.minecraft.client.Minecraft;
import net.minecraft.client.Screenshot;
import net.minecraft.client.gui.screens.TitleScreen;
import net.minecraft.world.Difficulty;
import net.minecraft.world.level.GameType;
import net.minecraft.world.level.LevelSettings;
import net.minecraft.world.level.WorldDataConfiguration;
import net.minecraft.world.level.levelgen.WorldOptions;
import net.minecraft.world.level.levelgen.presets.WorldPresets;

import java.io.IOException;
import java.lang.instrument.Instrumentation;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.concurrent.CompletableFuture;

/**
 * Java agent that drives the game from a script, for tests: no mod, nothing installed in the game.
 *
 * Script (one action per line, # for comments):
 *   world <name>          create a fresh flat creative test world (replacing any previous one) and join it
 *   wait <seconds>
 *   command <command>     run a command as the player, without the leading slash
 *   hud off|on            hide or show the HUD (like F1)
 *   screenshot <name>     save screenshots/<name>.png from the game's own framebuffer
 *   quit
 */
public class ShaderTestAgent {
    public static void premain(String args, Instrumentation inst) {
        Thread t = new Thread(() -> run(Path.of(args)), "shader-test-agent");
        t.setDaemon(true);
        t.start();
    }

    static void run(Path script) {
        try {
            List<String> lines = Files.readAllLines(script);
            Minecraft mc = awaitGame();
            for (String raw : lines) {
                String line = raw.strip();
                if (line.isEmpty() || line.startsWith("#")) {
                    continue;
                }
                String[] parts = line.split("\\s+", 2);
                String arg = parts.length > 1 ? parts[1] : "";
                log("> " + line);
                switch (parts[0]) {
                    case "world" -> openWorld(mc, arg);
                    case "wait" -> Thread.sleep((long) (Double.parseDouble(arg) * 1000));
                    case "command" -> onGameThread(mc, () -> mc.getConnection().sendCommand(arg));
                    case "hud" -> onGameThread(mc, () -> {
                        if (mc.gui.hud.isHidden() != arg.equals("off")) {
                            mc.gui.hud.toggle();
                        }
                    });
                    case "screenshot" -> onGameThread(mc, () -> Screenshot.grab(mc.gameDirectory, arg + ".png", mc.gameRenderer.mainRenderTarget(), 1,
                        message -> log("screenshot " + arg + ": " + message.getString())));
                    case "quit" -> onGameThread(mc, mc::stop);
                    default -> log("unknown action: " + parts[0]);
                }
            }
        } catch (Exception e) {
            log("failed: " + e);
            e.printStackTrace();
        }
    }

    static Minecraft awaitGame() throws InterruptedException {
        while (Minecraft.getInstance() == null || !Minecraft.getInstance().isGameLoadFinished()) {
            Thread.sleep(250);
        }
        Thread.sleep(1000);
        return Minecraft.getInstance();
    }

    static void openWorld(Minecraft mc, String name) throws Exception {
        // Always a fresh world: reproducible, and reopening a test world stops on an
        // "experimental settings" confirmation screen.
        Path save = mc.gameDirectory.toPath().resolve("saves").resolve(name);
        if (Files.exists(save)) {
            try (var files = Files.walk(save)) {
                for (Path p : files.sorted(java.util.Comparator.reverseOrder()).toList()) {
                    Files.delete(p);
                }
            }
        }
        onGameThread(mc, () -> {
            LevelSettings settings = new LevelSettings(name, GameType.CREATIVE,
                new LevelSettings.DifficultySettings(Difficulty.PEACEFUL, false, false), true, WorldDataConfiguration.DEFAULT);
            mc.createWorldOpenFlows().createFreshLevel(name, settings, WorldOptions.testWorldWithRandomSeed(),
                WorldPresets::createTestWorldDimensions, new TitleScreen());
        });
        while (mc.player == null || mc.level == null || mc.gui.screen() != null) {
            Thread.sleep(250);
        }
        log("in world " + name);
    }

    static void onGameThread(Minecraft mc, Runnable action) throws Exception {
        CompletableFuture<Void> done = new CompletableFuture<>();
        mc.execute(() -> {
            try {
                action.run();
                done.complete(null);
            } catch (Throwable e) {
                done.completeExceptionally(e);
            }
        });
        done.get();
    }

    static void log(String message) {
        System.out.println("[shader-test-agent] " + message);
    }
}
