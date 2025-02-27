import json
import subprocess
import os

def format_time(seconds):
    """将秒转换为 SRT 时间格式 (HH:MM:SS,mmm)"""
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    milliseconds = int((seconds - int(seconds)) * 1000)
    return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02},{milliseconds:03}"

def generate_srt_for_segment(sentences, output_srt):
    """生成分段视频的 SRT 字幕（时间轴基于段落起始时间偏移）"""
    srt_content = ""
    segment_start = sentences[0]["Start"]
    last_end = sentences[0]["Start"]
    gap = 0
    for idx, sentence in enumerate(sentences, 1):
        gap = sentence["Start"] - last_end + gap
        # print("srt", output_srt, idx, gap)
        
        start = (sentence["Start"]-segment_start - gap) / 1000
        end = (sentence["End"]-segment_start - gap) / 1000
        text = sentence["Text"]
        
        last_end = sentence["End"]
        
        srt_content += f"{idx}\n{format_time(start)} --> {format_time(end)}\n{text}\n\n"
    with open(output_srt, "w", encoding="utf-8") as f:
        f.write(srt_content)

def process_segment(input_video, sentences, output_dir, segment_name):
    """合并操作：截取视频 + 嵌入字幕（单步完成）"""
    # 1. 生成时间范围列表
    time_ranges = [(s["Start"] / 1000, s["End"] / 1000) for s in sentences]
    select_expr = "+".join([f"between(t,{start},{end})" for (start, end) in time_ranges])
    
    # # 2. 计算段落起始时间（第一个句子的起始时间）
    # segment_start = sentences[0]["Start"] / 1000
    
    # 3. 生成临时字幕文件
    srt_path = f"{output_dir}/{segment_name}.srt"
    generate_srt_for_segment(sentences, srt_path)
    
    # 4. 单步 FFmpeg 命令：截取视频 + 嵌入字幕
    final_video_path = f"{output_dir}/{segment_name}_final.mp4"
    cmd = [
        "ffmpeg",
        "-i", input_video,
        "-vf", f"select='{select_expr}',setpts=N/FRAME_RATE/TB,subtitles={srt_path}",  # 合并滤镜链
        "-af", f"aselect='{select_expr}',asetpts=N/SR/TB",
        "-c:v", "libx264",
        "-c:a", "aac",
        final_video_path
    ]
    # print(cmd)
    subprocess.run(cmd, check=True)
    
    # # 5. 清理临时字幕文件
    # os.remove(srt_path)

def main(json_file, input_video, output_dir):
    # # 解析 JSON 数据
    # with open(json_file, "r", encoding="utf-8") as f:
    #     data = json.load(f)
    
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    # 提取段落和句子信息
    auto_chapters = json.load(open('video/AutoChapters.json'))["AutoChapters"] # data["AutoChapters"]
    # text_polish = json.load(open('video/TextPolish.json'))["TextPolish"] # data["TextPolish"]
    # text_polish = {p["ParagraphId"]: p for p in text_polish}
    translation_paragraphs = json.load(open('video/Translation.json'))["Translation"]["Paragraphs"]
    
    # 按段落处理
    for chapter in auto_chapters:
        # print(chapter)
        # 匹配对应段落的句子
        paragraph_id = chapter["Id"]
        sentences = [s for paragraph in translation_paragraphs for s in paragraph['Sentences'] if s['Start'] >= chapter["Start"] and s['End'] <= chapter["End"]]
        
        # 处理分段
        segment_name = str(chapter["Id"]) + '-' + \
            chapter["Headline"].replace(" ", "_").replace("/", "_").replace(":", "_")
        process_segment(input_video, sentences, output_dir, segment_name)

if __name__ == "__main__":
    main("tingwu_result.json", "/Users/cn/sn/mvc/video/ENTAC_Lundberg-3.mp4", "output")