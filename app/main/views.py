from flask import render_template, session, redirect, url_for, current_app, request, flash, make_response, abort
from flask_login import current_user, login_required
from .. import db
from ..models import Post, Permission, Comment
from ..email import send_email
from . import main
from ..decorators import permission_required
from .forms import PostForm, CommentForm
from flask_sqlalchemy import get_debug_queries


@main.route('/', methods=['GET', 'POST'])
def index():
    form = PostForm()
    if current_user.can(Permission.WRITE_ARTICLES) and form.validate_on_submit():
        post = Post(body = form.body.data, author=current_user._get_current_object())
        db.session.add(post)
        db.session.commit()
        return redirect(url_for('.index'))

    show_followed = False
    if current_user.is_authenticated:
        show_followed = bool(request.cookies.get('show_followed', ''))

    if show_followed:
        query = current_user.followed_posts
    else:
        query = Post.query


    page = request.args.get('page', 1, type=int)
    pagination = query.order_by(Post.timestamp.desc()).paginate(
        page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
        error_out = False
      )
    posts = pagination.items
    return render_template('index.html', form=form, posts = posts, show_followed = show_followed, pagination=pagination)

@main.route('/all') 
@login_required 
def show_all():
    resp = make_response(redirect(url_for('.index'))) 
    resp.set_cookie('show_followed', '', max_age=30*24*60*60) 
    return resp

@main.route('/followed') 
@login_required
def show_followed():
    resp = make_response(redirect(url_for('.index'))) 
    resp.set_cookie('show_followed', '1', max_age=30*24*60*60) 
    return resp


@main.route('/post/<int:id>', methods=['Get', 'Post'])
def post(id):
    post = Post.query.get_or_404(id)
    form = CommentForm()
    if form.validate_on_submit():
        comment = Comment(body=form.body.data, post = post, author = current_user._get_current_object())
        db.session.add(comment)
        db.session.commit()
        return redirect(url_for('.post', id=post.id, page=-1))
    page = request.args.get('page', 1, type=int)
    if page == -1:
        page = (post.comments.count() -1) / current_app.config['FLASKY_COMMENTS_PER_PAGE']
    pagination = post.comments.order_by(Comment.timestamp.desc()).paginate(
        page, per_page=current_app.config['FLASKY_COMMENTS_PER_PAGE'], error_out=False)
    comments = pagination.items
    return render_template('post.html', posts=[post], form=form, comments = comments, pagination = pagination)

@main.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    post = Post.query.get_or_404(id)
    if current_user != post.author and not current_user.can(Permission.ADMINISTER):
        abort(403)
    form = PostForm()
    if form.validate_on_submit():
        post.body = form.body.data 
        db.session.add(post)
        db.session.commit()
        flash('The post has been updated.')
        return redirect(url_for('.post', id=post.id))
    form.body.data = post.body
    return render_template('edit_post.html', form=form)

@main.route('/moderate')
@login_required
@permission_required(Permission.MODERATE_COMMENTS)
def moderate():
    page = request.args.get('page', 1, type=int)
    pagination = Comment.query.order_by(Comment.timestamp.desc()).paginate(
        page, per_page = current_app.config['FLASKY_COMMENTS_PER_PAGE'],
        error_out = True)
    comments = pagination.items
    return render_template('moderate.html', comments = comments, pagination = pagination, page = page)


@main.route('/moderate/enable/<int:id>')
@login_required
@permission_required(Permission.MODERATE_COMMENTS)
def moderate_enable(id):
    comment = Comment.query.get_or_404(id)
    comment.disabled = False
    db.session.add(comment)
    db.session.commit()
    return redirect(url_for('.moderate', page=request.args.get('page', 1, type=int)))

@main.route('/moderate/disable/<int:id>') 
@login_required 
@permission_required(Permission.MODERATE_COMMENTS) 
def moderate_disable(id):
    comment = Comment.query.get_or_404(id) 
    comment.disabled = True 
    db.session.add(comment)
    return redirect(url_for('.moderate', page=request.args.get('page', 1, type=int)))

@main.after_app_request
def after_request(response):
    for query in get_debug_queries():
        if query.duration >= current_app.config['FLASKY_SLOW_DB_QUERY_TIME']: 
            current_app.logger.warning('Slow query: %s\nParameters: %s\nDuration: %fs\nContext: %s\n' % (query.statement, query.parameters, query.duration,query.context))

    return response



