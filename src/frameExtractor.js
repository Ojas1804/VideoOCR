import ffmpeg from 'fluent-ffmpeg';
import { path as ffmpegPath } from '@ffmpeg-installer/ffmpeg';
import { path as ffprobePath } from '@ffprobe-installer/ffprobe';
import { mkdirSync, readdirSync } from 'fs';
import { join } from 'path';

ffmpeg.setFfmpegPath(ffmpegPath);
ffmpeg.setFfprobePath(ffprobePath);

function parseFrameRate(str) {
  if (!str) return 25;
  const parts = str.split('/');
  if (parts.length === 2) {
    const [n, d] = parts.map(Number);
    return d ? n / d : n;
  }
  return Number(str) || 25;
}

/**
 * Returns basic metadata about a video file.
 * @param {string} videoPath
 * @returns {Promise<{fps:number, duration:number, width:number, height:number}>}
 */
export function getVideoInfo(videoPath) {
  return new Promise((resolve, reject) => {
    ffmpeg.ffprobe(videoPath, (err, metadata) => {
      if (err) return reject(new Error(`ffprobe failed: ${err.message}`));
      const stream = metadata.streams.find(s => s.codec_type === 'video');
      if (!stream) return reject(new Error('No video stream found'));
      resolve({
        fps:      parseFrameRate(stream.r_frame_rate),
        duration: parseFloat(metadata.format.duration) || 0,
        width:    stream.width,
        height:   stream.height,
      });
    });
  });
}

/**
 * Extract frames from a video at the given sample FPS.
 * Writes JPEG files to outputDir as frame_000001.jpg, frame_000002.jpg, …
 * Resolves with the number of frames written.
 *
 * @param {string} videoPath
 * @param {string} outputDir
 * @param {number} [sampleFps=2]
 * @returns {Promise<number>}
 */
export function extractFrames(videoPath, outputDir, sampleFps = 2.0) {
  mkdirSync(outputDir, { recursive: true });
  return new Promise((resolve, reject) => {
    ffmpeg(videoPath)
      .videoFilter(`fps=${sampleFps}`)
      .output(join(outputDir, 'frame_%06d.jpg'))
      .outputOptions(['-q:v', '2'])
      .on('end', () => {
        const count = readdirSync(outputDir).filter(f => f.endsWith('.jpg')).length;
        resolve(count);
      })
      .on('error', err => reject(new Error(`ffmpeg failed: ${err.message}`)))
      .run();
  });
}
