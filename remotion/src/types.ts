export interface SceneA {
  text: string;
  duration_sec: number;
  image_prompt: string;
}

export interface ModeAProps {
  scenes: SceneA[];
  imagePaths: string[];
  bgmPath: string | null;
}

export interface SceneB {
  text: string;
  duration_sec: number;
  image_prompt: string;
  source_timestamp_sec?: number;
}

export interface ModeBProps {
  scenes: SceneB[];
  sourceVideo: string;
}
