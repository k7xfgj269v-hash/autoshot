import React from "react";
import {
  AbsoluteFill,
  Audio,
  interpolate,
  OffthreadVideo,
  Sequence,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

interface Scene {
  text: string;
  duration_sec: number;
  source_timestamp_sec: number;
}

interface ModeBProps {
  scenes: Scene[];
  sourceVideo: string;
  title?: string;
  bgmPath?: string;
}

export const ModeB: React.FC<ModeBProps> = ({
  scenes,
  sourceVideo,
  title,
  bgmPath,
}) => {
  const { fps, durationInFrames } = useVideoConfig();
  const frame = useCurrentFrame();

  let offset = 0;
  const sequences = scenes.map((scene, i) => {
    const dur = Math.max(Math.round(scene.duration_sec * fps), 1);
    const from = offset;
    offset += dur;
    return (
      <Sequence key={i} from={from} durationInFrames={dur}>
        <AbsoluteFill>
          {/* 从 source_timestamp_sec 处开始截取原视频片段，静音播放 */}
          <OffthreadVideo
            src={staticFile(sourceVideo)}
            startFrom={Math.round((scene.source_timestamp_sec ?? 0) * fps)}
            muted
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
          {/* 字幕叠加 */}
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
      </Sequence>
    );
  });

  const fadeEnd = Math.min(90, durationInFrames - 1);
  const fadeStart = Math.min(75, fadeEnd - 1);
  const titleOpacity = interpolate(frame, [0, 15, fadeStart, fadeEnd], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill>
      {sequences}
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
      {bgmPath && <Audio src={staticFile(bgmPath)} volume={0.3} />}
    </AbsoluteFill>
  );
};
