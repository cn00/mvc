## movie clips

### 概述
用于视频剪辑的python库.

- 使用听悟 API 解析长视频, 获得带时间轴的语音文本和带起止时间分段信息
- 根据听悟的返回视频信息,使用 ffmpeg 选取每句语音文本对应的片段, 调整起止时间组装srt格式字幕, 将字幕和视频按段落组装合成分段视频

```sh
ffmpeg -i input.mp4 -vf "select='between(t,4,6.5)+between(t,17,26)+between(t,74,91)',setpts=N/FRAME_RATE/TB,subtitles=data/test.srt" \
-af "aselect='between(t,4,6.5)+between(t,17,26)+between(t,74,91)',asetpts=N/SR/TB" \
out.mp4
```