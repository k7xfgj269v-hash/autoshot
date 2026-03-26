import React from "react";
import { Composition, registerRoot } from "remotion";
import { ModeA } from "./ModeA";
import { ModeB } from "./ModeB";

const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="ModeA"
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        component={ModeA as React.ComponentType<any>}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={{
          scenes: [],
          imagePaths: [],
          title: "",
          bgmPath: undefined,
          voicePath: undefined,
        }}
        calculateMetadata={({ props }) => {
          const FPS = 30; // must match the fps prop on this Composition
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const scenes = (props as any).scenes as Array<{ duration_sec: number }>;
          const totalFrames = scenes.reduce(
            (sum: number, s: { duration_sec: number }) =>
              sum + Math.max(Math.round(s.duration_sec * FPS), 1),
            0
          );
          return { durationInFrames: totalFrames > 0 ? totalFrames : 300 };
        }}
      />
      <Composition
        id="ModeB"
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        component={ModeB as React.ComponentType<any>}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={{
          scenes: [],
          sourceVideo: "",
          title: "",
          bgmPath: undefined,
        }}
        calculateMetadata={({ props }) => {
          const FPS = 30; // must match the fps prop on this Composition
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const scenes = (props as any).scenes as Array<{ duration_sec: number }>;
          const totalFrames = scenes.reduce(
            (sum: number, s: { duration_sec: number }) =>
              sum + Math.max(Math.round(s.duration_sec * FPS), 1),
            0
          );
          return { durationInFrames: totalFrames > 0 ? totalFrames : 300 };
        }}
      />
    </>
  );
};

registerRoot(RemotionRoot);
