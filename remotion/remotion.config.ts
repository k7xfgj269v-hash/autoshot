import { Config } from "@remotion/cli/config";

Config.setVideoImageFormat("jpeg");
Config.setOverwriteOutput(true);
// Force software rendering to fix mirrored text on Windows headless Chromium
Config.setChromiumOpenGlRenderer("swiftshader");

