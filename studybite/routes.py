import os
import secrets
import sys
from PIL import Image
from flask import render_template, url_for, flash, redirect, request, abort, session
from studybite import app, db, bcrypt, socketio
from studybite.forms import RegForm, LogForm, PictureForm, PostForm, RequestForm, ReplyForm, GroupForm, PollForm
from studybite.models import User, Post, Requests, private_chats, private_messages, post_replies, Upvote, group_chats, group_messages, poll_data
from flask_login import login_user, current_user, logout_user, login_required
from flask_socketio import Namespace, emit, join_room, leave_room, \
    close_room, rooms, disconnect
from werkzeug import secure_filename

@app.route("/")
def home_redirect():
    return redirect(url_for('home', filter_id='all'))

@app.route("/home/<filter_id>")
def home(filter_id):
    # if current_user.is_authenticated:
    #     check = private_message_check()
    #     if check > 0:
    #         notification = str(check)+" messages"
    #     elif check <= 0:
    #         notification = "0 messages"
    # if not current_user.is_authenticated:
    #     notification = "0 messages"
    if filter_id == "all":
        posts = Post.query.all()
    elif filter_id == "votes":
        posts = Post.query.all()
        return render_template('home_upvotes.html', posts=posts)
    elif filter_id == "school_work" or "home_work" or "out_of_school" or "misc":
        posts = Post.query.filter_by(category=filter_id).all()
    return render_template('home.html', posts=posts) #notification=notification)

@app.route("/vote/<post_id>")
#handling of the votes, after a user presses upvote on a post
def upvote(post_id):
    check = Upvote.query.filter_by(post=post_id,user=current_user.id).first()
    if check:
        return redirect(url_for('home', filter_id='all'))
    else:
        #finds the post and increases the votes field in the Post table
        post = Post.query.filter_by(id=post_id).first()
        post.votes += 1
        #updates the upvote's table with the post that is being upvoted and by who
        vote = Upvote(post=post_id,user=current_user.id)
        db.session.add(vote)
        db.session.commit()
        return redirect(url_for('home', filter_id='all'))

# def private_message_check():
#     users_friends = current_user.friends.all()
#     for fr in users_friends:
#         users = [current_user.username,fr.username]
#         sorted_chat = sorted(users, reverse = False)
#         chat = private_chats.query.filter_by(name=sorted_chat[0]+'AND'+sorted_chat[1]).first()
#         ascending = private_messages.query.filter_by(chat_id=chat.id).all()
#         if ascending == []:
#             return(0)
#             break
#         u_dis = []
#         total = []
#         for x in ascending:
#             if x.message == current_user.username+"_DISCONNECTED":
#                 u_dis.append(x.id)
#             total.append(x.id)
#         if total[-1] > u_dis[-1]:
#             return(total[-1] - u_dis[-1])
#         else:
#             return(0)

@app.route("/chat_greeting", methods=['GET', 'POST'])
@login_required
def chat_greeting():
    users_friends = current_user.friends.all()
    username = current_user.username
    friend_dict = {}
    chats = []
    for fr in users_friends:
        users = [current_user.username,fr.username]
        chat = sorted(users, reverse = False)
        chat_id = chat[0]+'AND'+chat[1]
        friend_dict[fr.username] = chat_id
    for user_groups in current_user.uic_id:
        chats.append(group_chats.query.filter_by(id=user_groups.id).first())
    return render_template('chat_greeting.html', username=username, async_mode=socketio.async_mode, friends=friend_dict, chats=chats)

@app.route("/p_chat/<room_id>", methods=['GET', 'POST'])
@login_required
def p_chat(room_id):
    chat = private_chats.query.filter_by(name=room_id).first()
    if current_user.id == chat.user1 or chat.user2:
        messages = private_messages.query.filter_by(chat_id=chat.id).all()
        username = current_user.username
    else:
        flash('this is a private chat', 'danger')
        return redirect(url_for('chat_greeting'))
    return render_template('chat.html', username=username, async_mode=socketio.async_mode, room_id=room_id, messages=messages)

@app.route("/g_chat/<room_id>", methods=['GET', 'POST'])
@login_required
def g_chat(room_id):
    verified = False
    form = RequestForm()
    chat = group_chats.query.filter_by(name=room_id).first()
    for x in current_user.uic_id:
        if x.name == room_id:
            verified = True
    if verified == True:
        messages = group_messages.query.filter_by(chat_id=chat.id).all()
        username = current_user.username
        if form.validate_on_submit():
            for y in current_user.friends.all():
                if form.name.data == y.username:
                    friend = User.query.filter_by(username=y.username).first()
                    group = group_chats.query.filter_by(name=room_id).first()
                    friend.uic_id.append(group)
                    db.session.commit()
                    flash('you added the user', 'success')
                    return redirect(url_for('g_chat', room_id=room_id))
                else:
                    flash('enter a friends name', 'danger')
                    return redirect(url_for('g_chat'))
    elif verified == False:
        flash('you need an invite', 'danger')
        return redirect(url_for('chat_greeting'))
    return render_template('group_chat.html', room_id=room_id, username=username, async_mode=socketio.async_mode, messages=messages, form=form)

@app.route("/create_group", methods=['GET', 'POST'])
def create_group():
    not_allowed = '!"#$%&\'()*+,-./:;<=>?@[\\]^`{|}~ '
    passed = True
    form = GroupForm()
    if form.validate_on_submit():
        for x in range(0, len(form.name.data)):
            if form.name.data[x] in not_allowed:
                passed = False
        if passed == False:
            flash('request already sent', 'danger')
            return redirect(url_for('create_group'))
        elif passed == True:
            group = group_chats(name=form.name.data)
            db.session.add(group)
            group.chat_users.append(current_user)
            db.session.commit()
            flash('group chat created', 'success')
            return redirect(url_for('chat_greeting'))
    return render_template('create_group.html', form=form)

@app.route("/poll/new", methods=['GET', 'post'])
def create_poll():
    form = PollForm()
    topics = 2
    if form.validate_on_submit():
        if form.topic3.data != "":
            topics += 1
        if form.topic4.data != "":
            topics +=1
        if topics == 2:
            post = Post(title=form.title.data, category=form.category.data, author=current_user, poll=True)
            db.session.add(post)
            db.session.commit()
            post_search = Post.query.filter_by(title=form.title.data).first()
            topic_1 = poll_data(post=post_search.id, topic=form.topic1.data)
            topic_2 = poll_data(post=post_search.id, topic=form.topic2.data)
            db.session.add(topic_1)
            db.session.add(topic_2)
            db.session.commit()
        if topics == 3:
            post = Post(title=form.title.data, category=form.category.data, author=current_user, poll=True)
            db.session.add(post)
            db.session.commit()
            post_search = Post.query.filter_by(title=form.title.data).first()
            topic_1 = poll_data(post=post_search.id, topic=form.topic1.data)
            topic_2 = poll_data(post=post_search.id, topic=form.topic2.data)
            topic_3 = poll_data(post=post_search.id, topic=form.topic3.data)
            db.session.add(topic_1)
            db.session.add(topic_2)
            db.session.add(topic_3)
            db.session.commit()
        if topics == 4:
            post = Post(title=form.title.data, category=form.category.data, author=current_user, poll=True)
            db.session.add(post)
            db.session.commit()
            post_search = Post.query.filter_by(title=form.title.data).first()
            topic_1 = poll_data(post=post_search.id, topic=form.topic1.data)
            topic_2 = poll_data(post=post_search.id, topic=form.topic2.data)
            topic_3 = poll_data(post=post_search.id, topic=form.topic3.data)
            topic_4 = poll_data(post=post_search.id, topic=form.topic4.data)
            db.session.add(topic_1)
            db.session.add(topic_2)
            db.session.add(topic_3)
            db.session.add(topic_4)
            db.session.commit()
        flash('poll created', 'success')
        return redirect(url_for('home', filter_id='all'))
    else:
        pass
    return render_template('create_poll.html',form=form)

@app.route("/poll/<room_id>", methods=['GET', 'POST'])
@login_required
def poll(room_id):
    post = Post.query.filter_by(id=room_id).first()
    button = poll_data.query.filter_by(post=room_id).all()
    p_data = []
    for x in range(0, len(button)):
        temp = (button[x].topic, button[x].value)
        p_data.append(temp)
    return render_template('poll.html', username=current_user.username, async_mode=socketio.async_mode, room_id=room_id,
    p_data=p_data, post=post, button=button)

class PollApp(Namespace):
    def on_join(self, message):
        join_room(message['room'])

    def on_increment1(self, message):
        search = poll_data.query.filter_by(post=message['room']).all()
        search[0].value += 1
        db.session.commit()
        updated = poll_data.query.filter_by(post=message['room']).all()
        emit('response',
             {'data': str(updated[0].value), 'number': 1},
             room=message['room'])

    def on_increment2(self, message):
        search = poll_data.query.filter_by(post=message['room']).all()
        search[1].value += 1
        db.session.commit()
        updated = poll_data.query.filter_by(post=message['room']).all()
        emit('response',
             {'data': str(updated[1].value), 'number': 2},
             room=message['room'])

    def on_increment3(self, message):
        search = poll_data.query.filter_by(post=message['room']).all()
        search[2].value += 1
        db.session.commit()
        updated = poll_data.query.filter_by(post=message['room']).all()
        emit('response',
             {'data': str(updated[2].value), 'number': 3},
             room=message['room'])

    def on_increment4(self, message):
        search = poll_data.query.filter_by(post=message['room']).all()
        search[3].value += 1
        db.session.commit()
        updated = poll_data.query.filter_by(post=message['room']).all()
        emit('response',
             {'data': str(updated[3].value), 'number': 4},
             room=message['room'])

socketio.on_namespace(PollApp('/poll'))

class PrivateApp(Namespace):
    def on_my_event(self, message):
        emit('my_response',
             {'data': message['data']})

    def on_join(self, message):
        join_room(message['room'])
        room = private_chats.query.filter_by(name=message['room']).first()
        msg = private_messages(chat_id=room.id,
         message=current_user.username+'_CONNECTED', server_event='C', user=current_user.username)
        db.session.add(msg)
        db.session.commit()
        emit('my_response',
             {'data': 'USER CONNECTED', 'name': current_user.username})

    def on_send(self, message):
        room = private_chats.query.filter_by(name=message['room']).first()
        msg = private_messages(chat_id=room.id,
         message=message['data'], user=current_user.username)
        db.session.add(msg)
        db.session.commit()
        emit('my_response',
             {'data': message['data'], 'name': current_user.username},
             room=message['room'])

    def on_disconnect(self):
        whole = rooms()
        room = private_chats.query.filter_by(name=whole[1]).first()
        msg = private_messages(chat_id=room.id,
         message=current_user.username+'_DISCONNECTED', server_event='D', user=current_user.username)
        db.session.add(msg)
        db.session.commit()

socketio.on_namespace(PrivateApp('/privatechat'))

class GroupApp(Namespace):
    def on_my_event(self, message):
        emit('my_response',
             {'data': message['data']})

    def on_join(self, message):
        join_room(message['room'])
        room = group_chats.query.filter_by(name=message['room']).first()
        msg = group_messages(chat_id=room.id,
         message=current_user.username+'_CONNECTED', server_event='C', user=current_user.username)
        db.session.add(msg)
        db.session.commit()
        emit('my_response',
             {'data': 'USER CONNECTED', 'name': current_user.username})

    def on_send(self, message):
        room = group_chats.query.filter_by(name=message['room']).first()
        msg = group_messages(chat_id=room.id,
         message=message['data'], user=current_user.username)
        db.session.add(msg)
        db.session.commit()
        emit('my_response',
             {'data': message['data'], 'name': current_user.username},
             room=message['room'])

    def on_disconnect(self):
        print('Client disconnected', request.sid)
        whole = rooms()
        room = private_chats.query.filter_by(name=whole[1]).first()
        msg = group_messages(chat_id=whole[1],
         message=current_user.username+'_DISCONNECTED', server_event='D', user=current_user.username)
        db.session.add(msg)
        db.session.commit()

socketio.on_namespace(GroupApp('/groupchat'))

@app.route("/profile/<user_id>")
def profile(user_id):
    posts = Post.query.filter_by(user_id=user_id)
    return render_template('user_profile.html', posts=posts)

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
        return redirect(url_for('home', filter_id='all'))
    form = RegForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash('Your account has been created! You are now able to log in', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)


@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home', filter_id='all'))
    form = LogForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home', filter_id='all'))
        else:
            flash('check username and/or password', 'danger')
    return render_template('login.html', title='Login', form=form)


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('home', filter_id='all'))

def save_picture(form_picture):
    random = secrets.token_hex(8)
    file_name, file_extension = os.path.splitext(form_picture.filename)
    picture_name = random + file_extension
    picture_path = os.path.join(app.root_path, 'static/profile_pics', picture_name)
    size = (125, 125)
    i = Image.open(form_picture)
    i.thumbnail(size)
    i.save(picture_path)
    return picture_name

@app.route("/picture", methods=['GET', 'POST'])
@login_required
def picture():
    form = PictureForm()
    if form.validate_on_submit():
        if form.picture.data:
            picture_file = save_picture(form.picture.data)
            current_user.image_file = picture_file
        db.session.commit()
        flash('account has been updated', 'success')
        return redirect(url_for('picture'))
    image_file = url_for('static', filename='profile_pics/' + current_user.image_file)
    return render_template('picture.html', title='Account',
                           image_file=image_file, form=form)

@app.route("/post/new", methods=['GET', 'post'])
@login_required
def new_post():
    form = PostForm()
    if form.validate_on_submit():
        post = Post(title=form.title.data, content=form.content.data, author=current_user, category=form.category.data)
        db.session.add(post)
        db.session.commit()
        flash('posted', 'success')
        return redirect(url_for('home', filter_id='all'))
    else:
        print(form.errors)
    return render_template('create_post.html', title='New post',
                           form=form, legend='New post')

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
        flash('Updated', 'success')
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
    return redirect(url_for('home', filter_id='all'))

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
