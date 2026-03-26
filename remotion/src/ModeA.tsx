import React from "react";
import {
  AbsoluteFill,
  Audio,
  Img,
  interpolate,
  Sequence,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

interface Scene {
  text: string;
  duration_sec: number;
  image_prompt: string;
}

interface ModeAProps {
  scenes: Scene[];
  imagePaths: string[];
  title?: string;
  bgmPath?: string;
  voicePath?: string;
}

const SceneClip: React.FC<{
  scene: Scene;
  imagePath: string;
  durationInFrames: number;
}> = ({ scene, imagePath, durationInFrames }) => {
  const frame = useCurrentFrame();

  // Ken Burns 效果：图片从下往上缓慢移动
  const translateY = interpolate(frame, [0, Math.max(1, durationInFrames)], [0, -40], {
    extrapolateRight: "clamp",
  });

  // 淡入效果
  const opacity = interpolate(frame, [0, 8], [0, 1], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {/* 背景图片 */}
      <div
        style={{
          width: "100%",
          height: "100%",
          overflow: "hidden",
          opacity,
        }}
      >
        <Img
          src={staticFile(imagePath)}
          style={{
            width: "100%",
            height: "110%",
            objectFit: "cover",
            transform: `translateY(${translateY}px)`,
          }}
        />
      </div>

      {/* 字幕 */}
      <div
        style={{
          position: "absolute",
          bottom: 80,
          left: 0,
          right: 0,
          padding: "0 40px",
          textAlign: "center",
        }}
      >
        <span
          style={{
            fontSize: 48,
            fontWeight: "bold",
            color: "#ffffff",
            textShadow:
              "-2px -2px 0 #000, 2px -2px 0 #000, -2px 2px 0 #000, 2px 2px 0 #000",
            lineHeight: 1.4,
            display: "inline-block",
          }}
        >
          {scene.text}
        </span>
      </div>
    </AbsoluteFill>
  );
};

export const ModeA: React.FC<ModeAProps> = ({
  scenes,
  imagePaths,
  title,
  bgmPath,
  voicePath,
}) => {
  const { fps, durationInFrames } = useVideoConfig();
  const frame = useCurrentFrame();

  const fadeEnd = Math.min(90, durationInFrames - 1);
  const fadeStart = Math.min(75, fadeEnd - 1);
  const titleOpacity = interpolate(frame, [0, 15, fadeStart, fadeEnd], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  if (!imagePaths || imagePaths.length === 0) {
    return <AbsoluteFill style={{ backgroundColor: "black" }} />;
  }

  const sequences = scenes.reduce<{ elements: React.ReactNode[]; offset: number }>(
    (acc, scene, i) => {
      const durationInFrames = Math.round(scene.duration_sec * fps);
      const imgPath = imagePaths[i % imagePaths.length];
      const element = (
        <Sequence key={i} from={acc.offset} durationInFrames={durationInFrames}>
          <SceneClip
            scene={scene}
            imagePath={imgPath}
            durationInFrames={durationInFrames}
          />
        </Sequence>
      );
      return { elements: [...acc.elements, element], offset: acc.offset + durationInFrames };
    },
    { elements: [], offset: 0 }
  ).elements;

  return (
    <AbsoluteFill>
      {sequences}

      {/* 片头标题 */}
      {title && (
        <div
          style={{
            position: "absolute",
            top: 120,
            left: 0,
            right: 0,
            textAlign: "center",
            opacity: titleOpacity,
            padding: "0 60px",
          }}
        >
          <div
            style={{
              backgroundColor: "rgba(220, 20, 20, 0.85)",
              borderRadius: 12,
              padding: "16px 32px",
              display: "inline-block",
            }}
          >
            <span
              style={{
                fontSize: 52,
                fontWeight: "bold",
                color: "#fff",
                letterSpacing: 2,
              }}
            >
              {title}
            </span>
          </div>
        </div>
      )}

      {/* 配音（主音轨）*/}
      {voicePath && (
        <Audio src={staticFile(voicePath)} volume={1.0} />
      )}

      {/* BGM（配音存在时降低音量）*/}
      {bgmPath && (
        <Audio src={staticFile(bgmPath)} volume={voicePath ? 0.1 : 0.3} />
      )}
    </AbsoluteFill>
  );
};
