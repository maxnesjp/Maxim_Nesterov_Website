from flask import Flask, render_template, redirect, url_for, flash, abort, send_from_directory
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import LoginForm, RegisterForm, CreatePostForm, CommentForm, ContactForm, SecretKeyDownload
from flask_gravatar import Gravatar
import os
import requests
# pip install python-dotenv


SECRET_CODE = os.environ.get("SECRET_CODE")
TRUSTIFI_KEY = os.environ.get("TRUSTIFI_KEY")
TRUSTIFI_SECRET = os.environ.get("TRUSTIFI_SECRET")
TRUSTIFI_URL = os.environ.get("TRUSTIFI_URL")

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY")
ckeditor = CKEditor(app)
Bootstrap(app)
gravatar = Gravatar(app, size=100, rating='g', default='retro', force_default=False, force_lower=False, use_ssl=False,
                    base_url=None)

# -------------------------------CONNECT TO DB-------------------------------
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL", "sqlite:///blog.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    user = User.query.filter_by(id=int(user_id)).first()
    if user:
        return user
    return None


# -------------------------------CONFIGURE TABLES-------------------------------

class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)

    # Create Foreign Key, "users.id" the users refers to the tablename of User.
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    # Create reference to the User object, the "posts" refers to the posts property in the User class.

    author = relationship("User", back_populates="posts")
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)

    img_url = db.Column(db.String(250), nullable=False)
    comments = relationship("Comment", back_populates="parent_post")


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(100))

    # This will act like a List of BlogPost objects attached to each User.
    # The "author" refers to the author property in the BlogPost class.
    posts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comment", back_populates="comment_author")


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)

    post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    parent_post = relationship("BlogPost", back_populates="comments")
    comment_author = relationship("User", back_populates="comments")


# create the database


def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.id != 1:
            return abort(403)
        return f(*args, **kwargs)

    return decorated_function


@app.route('/')
def get_all_posts():
    db.create_all()
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts, current_user=current_user)


@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():

        if User.query.filter_by(email=form.email.data).first():
            print(User.query.filter_by(email=form.email.data).first())
            # User already exists
            flash("You've already signed up with that email, log in instead!")
            return redirect(url_for('login'))

        new_user = User(
            email=form.email.data,
            name=form.name.data,
            password=generate_password_hash(form.password.data, method='pbkdf2:sha256', salt_length=8)
        )
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for("get_all_posts"))

    return render_template("register.html", form=form, current_user=current_user)


@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        # Logging in the user to our website
        if not user:
            flash('This email does not exist.')
            return redirect(url_for('login'))
        elif not check_password_hash(password=form.password.data, pwhash=user.password):
            flash('Incorrect Password')
            return redirect(url_for('login'))
        else:
            # if the email corresponds to the existing email and the inputted password, then log the user in
            login_user(user)
            return redirect(url_for('get_all_posts'))
    return render_template("login.html", form=form, current_user=current_user)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    form = CommentForm()
    all_comments = Comment.query.filter_by(post_id=post_id).all()  # getting all comments for this post
    requested_post = BlogPost.query.get(post_id)

    if form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("You need to login or register to comment.")
            return redirect(url_for("login"))

        new_comment = Comment(
            text=form.comment_text.data,
            comment_author=current_user,
            parent_post=requested_post
        )
        db.session.add(new_comment)
        db.session.commit()
        return redirect(url_for('show_post', post_id=post_id))

    return render_template("post.html", post=requested_post, form=form, current_user=current_user,
                           comments=all_comments, gravatar=gravatar)



@app.route('/contact', methods=["POST", "GET"])
def contact_page():
    thanks_message = None
    # Create a form
    form = ContactForm()
    if form.validate_on_submit():
        name = form.name.data
        email = form.email_address.data
        phone = form.phone_number.data
        message = form.message_field.data
        thanks_message = "Successfully sent message"
        send_email_trustifi(name, email, phone, message)
        return render_template("contact.html", form=form, thanks_text=thanks_message)
    else:
        return render_template("contact.html", form=form, thanks_text=thanks_message)


def send_email_trustifi(name, email, phone, message):
    url = TRUSTIFI_URL + '/api/i/v1/email'
    bracket = "{"
    bracket2 = "}"
    our_message = f"Name:{name};   Phone number:{phone};   Email: {email};   Message:{message}"
    payload = f'{bracket}"recipients":[{bracket}"email":"maxnes500@gmail.com"{bracket2}],"title":"Message from Heroku","html":"{our_message}"{bracket2}'
    headers = {
        'x-trustifi-key': TRUSTIFI_KEY,
        'x-trustifi-secret': TRUSTIFI_SECRET,
        'Content-Type': 'application/json'
    }

    response = requests.request('POST', url, headers=headers, data=payload)
    print(response.json())



@app.route('/about', methods=["POST", "GET"])
def about():
    form = SecretKeyDownload()
    if form.validate_on_submit():
        if form.key.data == SECRET_CODE:
            return send_from_directory('static', filename="files/Resume_Maxim_Nesterov.pdf")
        else:
            flash('Incorrect code 😁')
            return redirect(url_for('about'))
    else:
        return render_template("about.html", current_user=current_user, form=form)


@app.route('/download')
@admin_only
def download():
    return send_from_directory('static', filename="files/Resume_Maxim_Nesterov.pdf")

@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))

    return render_template("make-post.html", form=form, current_user=current_user)


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=current_user,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form, is_edit=True, current_user=current_user)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    app.run(debug=True)
