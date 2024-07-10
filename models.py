import os
from sqlalchemy import create_engine, Column, String, Integer, DateTime, Text, JSON, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 初始化数据库
DATABASE_PATH = os.path.join(os.path.dirname(__file__), "weibo.db")  # 数据库存储位置
DATABASE_COPY_PATH = os.path.join(os.path.dirname(__file__), "weibo_copy.db")  # 备份数据库存储位置
os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
Base = declarative_base()


class BlogPost(Base):  # 博文对象定义

    __tablename__ = 'blogposts'
    id = Column(Integer, primary_key=True)  # 博文id
    username = Column(String)  # 博文发送者用户名
    text = Column(Text)  # 博文内容（已除去##话题）
    date = Column(DateTime)  # 博文发送时间
    reposts_count = Column(Integer)  # 博文转发数
    comments_count = Column(Integer)  # 博文评论数
    likes_count = Column(Integer)  # 博文点赞数
    topics = Column(JSON)  # 该博文相关的Topic的uuid列表
    keywords = Column(JSON, default=[])  # 关键词,字符串数组，留待分词程序提取关键词
    emotion = Column(JSON, default=[])  # 情感,情感数组，留待情感程序分析出情感


class Channel(Base):  # 微博频道定义
    __tablename__ = 'channels'
    title = Column(String)
    gid = Column(String, primary_key=True)
    containerid = Column(String)


class Weight(Base):  # 权重对象定义
    __tablename__ = 'weights'
    id = Column(Integer, primary_key=True)
    post_count_weight = Column(Float, default=0)
    avg_likes_weight = Column(Float, default=0)
    avg_comments_weight = Column(Float, default=0)
    avg_reposts_weight = Column(Float, default=0)


class Topic(Base):  # 话题对象定义
    __tablename__ = 'topics'
    topic_title = Column(String)  # 话题标题
    uuid = Column(String, primary_key=True)  # 话题UUID
    stage = Column(Integer, default=0)  # topic所处的生命周期的阶段，留待舆情预测软件进行预测
    post_count = Column(Integer, default=0)  # 主题相关博文数
    keywords = Column(JSON, default=[])  # 话题自身关键词,用于合并相似话题
    post_keywords = Column(JSON, default=[])  # 话题相关博文关键词及其词频，用于词云图和词频柱状图
    hot_rate = Column(Float, default=0)  # 话题热度，用于dashboard首页的话题统计图
    blogposts = Column(JSON, default=[])  # 话题相关博文的id列表
    emotion = Column(JSON, default=[])  # 情感，用于情感柱状图
    avg_likes = Column(Float, default=0)  # 平均点赞
    avg_comments = Column(Float, default=0)  # 平均评论
    avg_reposts = Column(Float, default=0)  # 平均转发
    hot_rate_per_hr = Column(JSON, default={})  # 每3小时的热度，用于时间-话题热度变化的柱状图


# 数据库使用SQLite，初始化会话
def get_Session(path):
    engine = create_engine(f'sqlite:///{path}')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session


Session = get_Session(DATABASE_PATH)
SessionCopy = get_Session(DATABASE_COPY_PATH)


# 从本地加载数据库
def load_database():
    db_session = Session()
    return db_session
