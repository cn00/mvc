import datetime
import os
import json
import time

import duckdb
import requests
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import CommonRequest
from aliyunsdkcore.auth.credentials import AccessKeyCredential

import dotenv
dotenv.load_dotenv()


def download_report(event, context):
    pass

# 音视频文件离线转写 
# https://help.aliyun.com/document_detail/2609582.html?spm=a2c4g.2619038.0.0.65a827b3zeGd9z
# https://nls-portal.console.aliyun.com/tingwu/overview?spm=a2c4g.11186623.0.0.304b31d2bzL3sn
class TingWuAgent:
    '''
    '''
    def __init__(self):
        self.credentials = AccessKeyCredential(
            os.environ['ALIBABA_CLOUD_ACCESS_KEY_ID'],
            os.environ['ALIBABA_CLOUD_ACCESS_KEY_SECRET']
        )
        self.client = AcsClient(region_id='cn-beijing', credential=self.credentials)

        db = duckdb.connect('./eshihui.duckdb')
        db.execute('''
            create table if not exists task(
                id          bigint,
                TaskId      varchar(256),
                TaskStatus  varchar(32),
                file_url    varchar(256)
                Result      text,
            );
            create table if not exists task_result (
                type        text, 
                TaskId      text, 
                content     text, 
                content_raw text
            )
        ''')
        self.db=db

    def get_parameters(self, url):
        body = dict()
        body['AppKey'] = os.getenv('ALIBABA_CLOUD_APP_KEY')  # '输入您在听悟管控台创建的Appkey'

        # 基本请求参数
        input = dict()
        input['SourceLanguage'] = 'cn'
        input['TaskKey'] = 'task' + datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        input['FileUrl'] = url  # '输入待测试的音频url链接'
        # input['ProgressiveCallbacksEnabled'] = True
        body['Input'] = input

        # AI相关参数，按需设置即可
        parameters = dict()

        # 音视频转换相关
        transcoding = dict()
        # 将原音视频文件转成mp3文件，用以后续浏览器播放
        # transcoding['TargetAudioFormat'] = 'mp3'
        # transcoding['SpectrumEnabled'] = False
        # parameters['Transcoding'] = transcoding

        # 语音识别控制相关
        transcription = dict()
        # 角色分离 ： 可选
        transcription['DiarizationEnabled'] = True
        diarization = dict()
        diarization['SpeakerCount'] = 2
        transcription['Diarization'] = diarization
        parameters['Transcription'] = transcription

        # 文本翻译控制相关 ： 可选
        parameters['TranslationEnabled'] = True
        translation = dict()
        translation['TargetLanguages'] = ['en']  # 假设翻译成英文
        parameters['Translation'] = translation

        # 章节速览相关 ： 可选，包括： 标题、议程摘要
        parameters['AutoChaptersEnabled'] = True

        # 智能纪要相关 ： 可选，包括： 待办、关键信息(关键词、重点内容、场景识别)
        parameters['MeetingAssistanceEnabled'] = True
        meetingAssistance = dict()
        meetingAssistance['Types'] = ['Actions', 'KeyInformation']
        parameters['MeetingAssistance'] = meetingAssistance

        # 摘要控制相关 ： 可选，包括： 全文摘要、发言人总结摘要、问答摘要(问答回顾)
        parameters['SummarizationEnabled'] = True
        summarization = dict()
        summarization['Types'] = ['Paragraph', 'Conversational', 'QuestionsAnswering']
        parameters['Summarization'] = summarization

        # ppt抽取和ppt总结 ： 可选
        parameters['PptExtractionEnabled'] = True

        # 口语书面化 ： 可选
        parameters['TextPolishEnabled'] = True

        body['Parameters'] = parameters
        return body

    def get_request(self, method, uri):
        request = CommonRequest()
        request.set_accept_format('json')
        request.set_domain('tingwu.cn-beijing.aliyuncs.com')
        request.set_version('2023-09-30')
        request.set_protocol_type('https')
        request.set_method(method)
        request.set_uri_pattern(uri)
        request.add_header('Content-Type', 'application/json')
        return request

    def add_task(self, file_url):
        db = self.db
        items = db.query('''
            select * from main.task 
            where file_url = ?
        ''', [file_url]).fetchall()
        if len(items) > 0:
            return
        
        request = self.get_request('PUT', '/openapi/tingwu/v2/tasks')
        request.add_query_param('type', 'offline')

        request.set_content(json.dumps(self.get_parameters(file_url)).encode('utf-8'))
        response = self.client.do_action_with_exception(request)
        print("request response: \n" + json.dumps(json.loads(response), indent=2, ensure_ascii=False))
        # {
        #     "Code":"0",
        #     "Data":{
        #         "TaskId":"e8adc0b3vc4b45d898fcadb*********",
        #         "TaskKey":"task16988********",
        #         "TaskStatus":"ONGOING"
        #     },
        #     "Message":"success",
        #     "RequestId":"2001dc2a-9b46-4a2f-9822-b140********"
        # }
        jsres = json.loads(response)
        db.execute('''
            insert into task (file_url, TaskId) values (?, ?)
        ''', [file_url, jsres['Data']['TaskId']])
        return jsres

    def check_result_all(self):
        '''
        '''
        db = self.db
        loop = True
        while loop:
            items = db.query('''
                select TaskId from main.task 
                where TaskStatus != 'COMPLETED' or TaskStatus is null
            ''').fetchall()
            if len(items)<1:
                break
            for it in items:
                TaskId = it[0]
                print(f'check_result TaskId: {TaskId}')
                self.check_result_one(str(TaskId))
                time.sleep(3)

    def check_result_one(self, TaskId):
        db = self.db
        request = self.get_request('GET', '/openapi/tingwu/v2/tasks' + '/' + TaskId)  # 请输入您提交任务时返回的
        response = self.client.do_action_with_exception(request)
        # print("check_result response: \n" + json.dumps(json.loads(response), indent=2, ensure_ascii=False))
        jsres = json.loads(response)
        # {
        #   "Code": "0",
        #   "Data": {
        #     "Result": {
        #       "AutoChapters":[]
        #       "MeetingAssistance": []
        #       ...
        #     },
        #     "TaskId": "f2e8f9b25a6345bda86cc83cb481ac76",
        #     "TaskKey": "task20240205151611",
        #     "TaskStatus": "COMPLETED"
        #    },
        #    "Message": "success",
        #    "RequestId": "F728A1B2-9503-538D-AFBB-6F9082755CC0"
        # }
        print(jsres['Data']['TaskStatus'])
        if jsres['Data']['TaskStatus'] == 'COMPLETED':
            # fetch result content: AutoChapters, MeetingAssistance,PptExtraction,
            # Summarization,TextPolish, Transcription, Translation
            result : dict = jsres['Data']['Result']
            for k in result.keys():
                v = result.get(k)
                text = requests.get(v, timeout=300).text
                res = json.loads(text)
                print(k,res)
                if k in res.keys():
                    db.execute('''
                        insert into task_result (type, TaskId, content, content_raw)
                        values (?, ?, ?, ?)
                    ''', [k, TaskId, json.dumps(res[k], ensure_ascii=False), text])

            # df['file_url'] = file_url
            # db = duckdb.connect(':memory:')
            # # s3://snn-eshihui-es/video/task
            # db.execute('''
            #     SET home_directory='/root';
            #     SET temp_directory='/tmp/duckdb';
            # ''')
            # db.execute(f'''
            #     SET s3_endpoint = 's3.cn-northwest-1.amazonaws.com.cn';
            #     CALL load_aws_credentials();
            #     copy (select * from df) to 's3://snn-eshihui-es/video-task/ONGOING/{task_id}.csv';
            # ''')

            db.execute('''
                update task set
                TaskStatus = ?,
                Result = ?
                where TaskId = ?
            ''', [jsres['Data']['TaskStatus'], json.dumps(jsres['Data']['Result'], ensure_ascii=False), TaskId])
        return jsres


# class MovieAgent:
    def cut_video_by_chapters(input_file, chapters, output_folder):
        """
        根据章节信息裁剪视频并保存为多个短视频
        :param input_file: 输入视频文件路径
        :param chapters: 章节信息（JSON 中的 AutoChapters）
        :param output_folder: 输出文件夹路径
        """
        from moviepy.editor import VideoFileClip

        # 加载视频
        video = VideoFileClip(input_file)

        for chapter in chapters:
            # 获取章节信息
            start_time = chapter["Start"] / 1000  # 转换为秒
            end_time = chapter["End"] / 1000      # 转换为秒
            headline = chapter["Headline"]        # 章节标题

            # 裁剪视频
            clip = video.subclip(start_time, end_time)

            # 生成输出文件名
            output_file = f"{output_folder}/{headline}.mp4"

            # 保存裁剪后的视频
            clip.write_videofile(output_file, codec="libx264")
            print(f"已保存: {output_file}")

        # 关闭视频对象
        video.close()

def convert_translation_to_srt(json_data, output_file):
    """
    将听悟 Translation 部分的 JSON 字幕转换为 SRT 格式
    :param json_data: 听悟返回的 JSON 数据
    :param output_file: 输出的 SRT 文件路径
    """
    paragraphs = json_data.get("Translation", {}).get("Paragraphs", [])
    srt_content = ""
    srt_index = 1

    for paragraph in paragraphs:
        sentences = paragraph.get("Sentences", [])
        for sentence in sentences:
            # 获取句子信息
            start = sentence["Start"]
            end = sentence["End"]
            text = sentence["Text"]

            # 转换时间格式
            start_time = format_time(start)
            end_time = format_time(end)

            # 生成 SRT 条目
            srt_content += f"{srt_index}\n"
            srt_content += f"{start_time} --> {end_time}\n"
            srt_content += f"{text}\n\n"
            srt_index += 1

    # 写入文件
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(srt_content)
    print(f"SRT 文件已保存: {output_file}")

def convert_json_to_srt(json_data, output_file):
    """
    将听悟返回的 JSON 字幕转换为 SRT 格式
    :param json_data: 听悟返回的 JSON 数据
    :param output_file: 输出的 SRT 文件路径
    """
    paragraphs = json_data.get("Paragraphs", [])
    srt_content = ""

    # 遍历段落
    for index, paragraph in enumerate(paragraphs, start=1):
        for sentenceIdx, sentence in enumerate(paragraph["Sentences"], start=1):
            # 获取单句信息
            start_time = format_time(sentence["Start"])
            end_time = format_time(sentence["End"])
            text = sentence["Text"]
            sentenceId = sentence["SentenceId"]

            # 生成 SRT 格式的内容
            srt_content += f"{sentenceId}\n"
            srt_content += f"{start_time} --> {end_time}\n"
            srt_content += f"{text}\n\n"

    # 将内容写入 SRT 文件
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(srt_content)
    print(f"SRT 文件已保存: {output_file}")

def convert_to_srt(data, output_file):
    with open(output_file, 'w') as f:
        count = 1
        for paragraph in data['Translation']['Paragraphs']:
            for sentence in paragraph['Sentences']:
                start_time = str(datetime.fromtimestamp(sentence['Start'] / 1000))
                end_time = str(datetime.fromtimestamp(sentence['End'] / 1000))
                text = sentence['Text']
                f.write(f"{count}\n{start_time} --> {end_time}\n{text}\n\n")
                count += 1


def format_time(milliseconds):
    """
    将毫秒转换为 SRT 时间格式 (HH:MM:SS,mmm)
    :param milliseconds: 毫秒时间戳
    :return: 格式化后的时间字符串
    """
    seconds, milliseconds = divmod(milliseconds, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"
