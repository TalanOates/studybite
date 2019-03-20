from datetime import datetime
from studybite import db, login_manager
from flask_login import UserMixin

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

friends = db.Table('friends',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('friend_id', db.Integer, db.ForeignKey('user.id'))
)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    image_file = db.Column(db.String(20), nullable=False, default='default.jpg')
    password = db.Column(db.String(60), nullable=False)
    posts = db.relationship('Post', backref='author', lazy=True)
    replies = db.relationship('post_replies', backref='user_replies', lazy=True)

    friends = db.relationship('User', #defining the relationship, User is left side entity
        secondary = friends,
        primaryjoin = (friends.c.user_id == id),
        secondaryjoin = (friends.c.friend_id == id),
        lazy = 'dynamic'
    )

    def __repr__(self):
        return f"User('{self.username}', '{self.email}', '{self.image_file}')"

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    replies = db.relationship('post_replies', backref='replies', lazy=True)
    votes = db.Column(db.Integer, nullable=True, default=0)

    def __repr__(self):
        return f"Post('{self.title}', '{self.date_posted}')"

class post_replies(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    votes = db.Column(db.Integer, nullable=True, default=0)


class Requests(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    user_f = db.Column(db.Integer)
    user_t = db.Column(db.Integer)

    def __repr__(self):
        return f"Post('{self.user_f}', '{self.user_t}')"

class private_chats(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), nullable=False)
    user1 = db.Column(db.String(20), nullable=False)
    user2 = db.Column(db.String(20), nullable=False)
    message = db.relationship('private_messages', backref='chat', lazy=True)

class private_messages(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.Integer, db.ForeignKey('private_chats.id'), nullable=False)
    date_time = db.Column(db.DateTime(), default=datetime.now())
    user = db.Column(db.String(20), nullable=False)
    message = db.Column(db.Text, nullable=False)
    server_event = db.Column(db.String(100), nullable=True)
