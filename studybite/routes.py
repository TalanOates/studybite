import os
import secrets
import sys
from PIL import Image
from flask import render_template, url_for, flash, redirect, request, abort, session
from studybite import app, db, bcrypt, socketio
from studybite.forms import RegistrationForm, LoginForm, UpdateAccountForm, PostForm, RequestForm, ReplyForm
from studybite.models import User, Post, Requests, private_chats, private_messages, post_replies
from flask_login import login_user, current_user, logout_user, login_required
from flask_socketio import Namespace, emit, join_room, leave_room, \
    close_room, rooms, disconnect

@app.route("/")
@app.route("/home")
def home():
    posts = Post.query.all()
    return render_template('home.html', posts=posts)

@app.route("/chat_greeting", methods=['GET', 'POST'])
@login_required
def chat_greeting():
    users_friends = current_user.friends.all()
    username = current_user.username
    form = RequestForm()
    if form.validate_on_submit():
        friend_id = User.query.filter_by(username = form.name.data).first()
        if friend_id:
            users = sorted([current_user.username, form.name.data], reverse=False)
            chat_users = private_chats.query.filter_by(user1=users[0],user2=users[1]).first()
            return redirect(url_for('chat', room_id=chat_users.name))
        else:
            flash('please enter a friend'+'s name', 'danger')
    return render_template('chat_greeting.html', username=username, async_mode=socketio.async_mode, form=form, friends=users_friends)

@app.route("/chat/<room_id>", methods=['GET', 'POST'])#"/chat/<session_id>
@login_required
def chat(room_id):
    messages = private_messages.query.filter_by(chat_id=room_id).all()
    username = current_user.username
    return render_template('chat.html', username=username, async_mode=socketio.async_mode, room_id=room_id, messages=messages)

class MyNamespace(Namespace):
    def on_my_event(self, message):
        emit('my_response',
             {'data': message['data']})

    def on_join(self, message):
        join_room(message['room'])
        room = private_chats.query.filter_by(name=message['room']).first()
        msg = private_messages(chat_id=room.id,
         message='USER CONNECTED', server_event='C', user=current_user.username)
        db.session.add(msg)
        db.session.commit()
        emit('my_response',
             {'data': 'USER CONNECTED', 'name': current_user.username})

    def on_my_room_event(self, message):
        room = private_chats.query.filter_by(name=message['room']).first()
        hashed_password = bcrypt.generate_password_hash(message['data']).decode('utf-8')
        msg = private_messages(chat_id=room.id,
         message=message['data'], user=current_user.username)
        db.session.add(msg)
        db.session.commit()
        emit('my_response',
             {'data': message['data'], 'name': current_user.username},
             room=message['room'])

    def on_disconnect(self):
        print('Client disconnected', request.sid)
        whole = rooms()
        msg = private_messages(chat_id=whole[1],
         message='USER DISCONNECTED', server_event='D', user=current_user.username)
        db.session.add(msg)
        db.session.commit()

socketio.on_namespace(MyNamespace('/test'))

@app.route("/profile/<user_id>")
def profile(user_id):
    posts = Post.query.filter_by(user_id=user_id)
    return render_template('home.html', posts=posts)

@app.route("/search", methods=['GET', 'POST'])
@login_required
def search():
    form = RequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.name.data).first()
        if form.name.data == current_user.username:
            flash('You are trying to send a request to yourself', 'danger')
            return redirect(url_for('search'))
        elif user:
            req = Requests(user_f=current_user.username, user_t=form.name.data)
            req_check = Requests.query.filter_by(user_f=current_user.username, user_t=form.name.data).first()
            if req_check:
                flash('request already sent', 'danger')
                return redirect(url_for('search'))
            else:
                db.session.add(req)
                db.session.commit()
                flash('User found, and request sent', 'success')
                return redirect(url_for('search'))
        else:
            flash('User not found, no request sent', 'danger')
    return render_template('search.html', title='Search', form=form)

@app.route("/friends", methods=['GET'])
@login_required
def friends():
    friends = current_user.friends
    return render_template('friends.html', title='Friends', friends=friends)

@app.route("/requests", methods=['GET'])
@login_required
def requests():
    request = Requests.query.filter_by(user_t=current_user.username).all()
    return render_template('requests.html', title='Requests', request=request)

@app.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data, email=form.email.data, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash('Your account has been created! You are now able to log in', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)


@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            flash('Login Unsuccessful. Please check email and password', 'danger')
    return render_template('login.html', title='Login', form=form)


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('home'))

def save_picture(form_picture):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(app.root_path, 'static/profile_pics', picture_fn)

    output_size = (125, 125)
    i = Image.open(form_picture)
    i.thumbnail(output_size)
    i.save(picture_path)

    return picture_fn

@app.route("/account", methods=['GET', 'POST'])
@login_required
def account():
    form = UpdateAccountForm()
    if form.validate_on_submit():
        if form.picture.data:
            picture_file = save_picture(form.picture.data)
            current_user.image_file = picture_file
        current_user.username = form.username.data
        current_user.email = form.email.data
        db.session.commit()
        flash('Your account has been updated!', 'success')
        return redirect(url_for('account'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.email.data = current_user.email
    image_file = url_for('static', filename='profile_pics/' + current_user.image_file)
    return render_template('account.html', title='Account',
                           image_file=image_file, form=form)

@app.route("/post/new", methods=['GET', 'POST'])
@login_required
def new_post():
    form = PostForm()
    if form.validate_on_submit():
        post = Post(title=form.title.data, content=form.content.data, author=current_user)
        db.session.add(post)
        db.session.commit()
        flash('Your post has been created!', 'success')
        return redirect(url_for('home'))
    return render_template('create_post.html', title='New Post',
                           form=form, legend='New Post')

@app.route("/post/<int:post_id>")
def post(post_id):
    replies = post_replies.query.filter_by(post_id=post_id).all()
    post = Post.query.get_or_404(post_id)
    return render_template('post.html', title=post.title, post=post, replies=replies)

@app.route("/post/<int:post_id>/reply", methods=['GET', 'POST'])
def post_reply(post_id):
    form = ReplyForm()
    post = Post.query.filter_by(id=post_id).first()
    if form.validate_on_submit():
        reply = post_replies(content=form.content.data, post_id=post_id, user_replies=current_user)
        db.session.add(reply)
        db.session.commit()
        return redirect(url_for('post', post_id=post_id))
    return render_template('reply_post.html', post=post, form=form)

@app.route("/post/<int:post_id>/update", methods=['GET', 'POST'])
@login_required
def update_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user:
        abort(403)
    form = PostForm()
    if form.validate_on_submit():
        post.title = form.title.data
        post.content = form.content.data
        db.session.commit()
        flash('Your post has been updated!', 'success')
        return redirect(url_for('post', post_id=post.id))
    elif request.method == 'GET':
        form.title.data = post.title
        form.content.data = post.content
    return render_template('create_post.html', title='Update Post',
                           form=form, legend='Update Post')

@app.route("/post/<int:post_id>/delete", methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user:
        abort(403)
    db.session.delete(post)
    db.session.commit()
    flash('Your post has been deleted!', 'success')
    return redirect(url_for('home'))

@app.route("/request/<int:request_id>/delete", methods=['POST'])
def delete_request(request_id):
    request = Requests.query.get_or_404(request_id)
    db.session.delete(request)
    db.session.commit()
    flash('You rejected the request', 'danger')
    return redirect(url_for('requests'))

@app.route("/request/<int:request_id>/accept", methods=['POST'])
def accept_request(request_id):
    request = Requests.query.get_or_404(request_id)
    user_f = User.query.filter_by(username=request.user_f).first()
    users = sorted([request.user_f, request.user_t], reverse=False)
    if user_f not in current_user.friends:
        chat_users = private_chats(name=users[0]+'AND'+users[1], user1=users[0], user2=users[1])
        db.session.add(chat_users)
        current_user.friends.append(user_f)
        user_f.friends.append(current_user)
    db.session.delete(request)
    db.session.commit()
    flash('friend request accepted', 'success')
    return redirect(url_for('requests'))
