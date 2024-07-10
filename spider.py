import re
import threading
import time
from datetime import datetime, timedelta
import jieba
import requests
from sqlalchemy import exists
from db_operations import display_topics
from topic_emotion import analyze_sentiment
from models import Session, Channel, Topic, BlogPost
from data_preprocessing import merge_topics
from text_analysis import extract_topic_keywords, extract_post_keywords, extract_keywords


# 将博文文本中的##话题清除
def clean_text(raw_text):
    return re.sub(r"#.*?#", "", raw_text).strip()


def fetch_channel_data():
    session = create_session()
    url = "https://weibo.com/ajax/feed/allGroups?is_new_segment=1&fetch_hot=1"
    response = session.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        raise RuntimeError("Failed to fetch channel data")


def save_channels_to_db():
    db_session = Session()
    groups = fetch_channel_data()['groups']
    for group in groups:
        if group['title'] in ["我的频道", "频道推荐"]:
            for channel in group['group']:
                new_channel = Channel(
                    title=channel['title'],
                    gid=channel['gid'],
                    containerid=channel['containerid']
                )
                print(new_channel.title, new_channel.gid, new_channel.containerid)
                db_session.merge(new_channel)
    db_session.commit()


# 从响应中获取JSON数据
def fetch_data(url, session):
    response = session.get(url)

    if response.status_code == 200:
        try:
            return response.json()
        except ValueError:
            print("Error: Unable to parse JSON response")
            print(response.content)
    else:
        print(f"Failed to fetch data from {url}, status code: {response.status_code}")
        print(response.content)


# 从JSON数据中提取需要的部分，并保存到数据库
def parse_and_store_data(data, db_session):
    for status in data['statuses']:
        post_id = status['id']
        username = status['user']['screen_name']
        text = clean_text(status['text_raw'])
        date = datetime.strptime(status['created_at'], '%a %b %d %H:%M:%S +0800 %Y')
        reposts_count = status['reposts_count']
        comments_count = status['comments_count']
        likes_count = status['attitudes_count']
        topics = []

        # 检测 BlogPost 的时间，如果超过 72 小时，则不插入数据库
        if datetime.now() - date > timedelta(hours=72):
            continue

        # 重复博文校验
        if not db_session.query(exists().where(BlogPost.id == post_id)).scalar():
            for topic in status.get('topic_struct', []):
                topic_title = topic['topic_title']
                topic_uuid = topic['actionlog']['uuid']
                topics.append({'uuid': topic_uuid})
                existing_topic = db_session.query(Topic).filter_by(uuid=topic_uuid).first()
                if not existing_topic:
                    # 如果该话题不存在，创建新的话题对象，并将post_count初始化为1
                    existing_topic = Topic(uuid=topic_uuid, topic_title=topic_title, blogposts=[post_id], post_count=1)
                    db_session.add(existing_topic)
                else:
                    # 如果该话题已存在，更新话题的博文数，并将博文ID添加到话题的博文列表中
                    existing_topic.post_count += 1
                    if post_id not in existing_topic.blogposts:
                        existing_topic.blogposts.append(post_id)

            sentiment_data = analyze_sentiment(list(jieba.cut(text)))
            new_post = BlogPost(
                id=post_id,
                username=username,
                text=text,
                date=date,
                reposts_count=reposts_count,
                comments_count=comments_count,
                likes_count=likes_count,
                topics=topics,
                emotion=sentiment_data
            )
            db_session.add(new_post)
            db_session.commit()
    db_session.close()


# 爬取函数
def spider(db_session, web_session, url, thread_id, num_requests):
    db_session = db_session()
    for i in range(num_requests):
        try:
            data = fetch_data(url, web_session)
            parse_and_store_data(data, db_session)
            print(f"线程{thread_id} - 第{i + 1}次爬取成功")
        except RuntimeError:
            print(f"线程{thread_id} - 第{i + 1}次爬取失败")


# 创建web会话
def create_session():
    session = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6,pl;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,'
                  'application/signed-exchange;v=b3;q=0.7',
        'Cookie': 'XSRF-TOKEN=8_SWaMKut4rHoV0gKxbosU-w; '
                  'SUB=_2AkMR3iVbf8NxqwFRmfwTym_gb491wwrEieKngtSAJRMxHRl-yj9kqlAdtRB6Ol4LtMT2_nw3nJBE6iHBC3BBwxDfnYD9'
                  '; SUBP=0033WrSXqPxfM72-Ws9jqgMF55529P9D9WWmOTlu_sjAigaiNAWJ-jCI; '
                  'WBPSESS=Wk6CxkYDejV3DDBcnx2LOYUlCFhUFP4kEWctmi37x8FAAnwquPbxTFonYDBuWjSW'
                  '-71uT6IFv_d7DhJseJBzopETW2qmDEF_cLkj8djgtyD-qVTf6OIIJ8FZZMigxeWb '
    }
    session.headers = headers
    return session


def multi_thread(db_session, urls, num_requests_per_thread=5):
    time_start = time.time()
    for i in range(0, len(urls), 3):
        threads = []
        for j in range(3):
            if i + j < len(urls):
                web_session = create_session()
                if i == 0:
                    t = threading.Thread(target=spider,
                                         args=(db_session, web_session, urls[i + j], j, 50))
                else:
                    t = threading.Thread(target=spider,
                                         args=(db_session, web_session, urls[i + j], j, num_requests_per_thread))
                threads.append(t)
                t.start()
        for t in threads:
            t.join()

        extract_keywords(db_session())
        display_topics(db_session())

    time_end = time.time()
    print('多线程爬取用时为', time_end - time_start, 's')


def multi_spider(db_session, num_requests_per_thread=8):
    url1 = "https://weibo.com/ajax/feed/hottimeline?since_id=0&refresh="
    url2 = "&group_id="
    url3 = "&containerid="
    url4 = "&extparam=discover%7Cnew_feed&max_id=0&count=10"

    save_channels_to_db()
    channels = db_session().query(Channel).all()
    urls = []
    for i in range(0, 3):
        for channel in channels:
            urls.append(url1 + f"{i}" + url2 + f"{channel.gid}" + url3 + f"{channel.containerid}" + url4)
    print(urls)
    multi_thread(db_session, urls, num_requests_per_thread)
