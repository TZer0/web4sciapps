import os
from compute import compute_gamma as compute_function

from flask import Flask, render_template, request, redirect, url_for
from forms import GammaForm
from db_models import db, User, Gamma
from flask.ext.login import LoginManager, current_user, login_user, logout_user, login_required
from app import app

login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return db.session.query(User).get(user_id)

# Path to the web application
@app.route('/', methods=['GET', 'POST'])
def index():
    result = None
    user = current_user
    form = GammaForm(request.form)
    if request.method == "POST":
        if form.validate():


            result = compute(form)
            if user.is_authenticated():
                object = Gamma()
                form.populate_obj(object)
                object.result = result
                object.user = user
                db.session.add(object)
                db.session.commit()

                # Send email notification
                if user.notify and user.email:
                    send_email(user)

    else:
        if user.is_authenticated():
            if user.Gamma.count() > 0:
                instance = user.Gamma.order_by('-id').first()
                result = instance.result
                form = populate_form_from_instance(instance)

    return render_template("view.html", form=form, result=result, user=user)

def compute(form):
    """
    Generic function for compute_function with arguments
    taken from a form object (wtforms.Form subclass).
    Return the output from the compute_function.
    """
    # Extract arguments to the compute function
    import inspect
    arg_names = inspect.getargspec(compute_function).args

    # Extract values from form
    form_values = [getattr(form, name) for name in arg_names
                   if hasattr(form, name)]

    form_data = [value.data for value in form_values]

    defaults  = inspect.getargspec(compute_function).defaults

    # Make defaults as long as arg_names so we can traverse both with zip
    if defaults:
        defaults = ["none"]*(len(arg_names)-len(defaults)) + list(defaults)
    else:
        defaults = ["none"]*len(arg_names)

    # Convert form data to the right type:
    import numpy
    for i in range(len(form_data)):
        if defaults[i] != "none":
            if isinstance(defaults[i], (str,bool,int,float)):
                pass  # special widgets for these types do the conversion
            elif isinstance(defaults[i], numpy.ndarray):
                form_data[i] = numpy.array(eval(form_data[i]))
            elif defaults[i] is None:
                if form_data[i] == 'None':
                    form_data[i] = None
                else:
                    try:
                        # Try eval if it succeeds...
                        form_data[i] = eval(form_data[i])
                    except:
                        pass # Just keep the text
            else:
                # Use eval to convert to right type (hopefully)
                try:
                    form_data[i] = eval(form_data[i])
                except:
                    print 'Could not convert text %s to %s for argument %s' % (form_data[i], type(defaults[i]), arg_names[i])
                    print 'when calling the compute function...'

    # Run computations
    result = compute_function(*form_data)
    return result

def populate_form_from_instance(instance):
    """Repopulate form with previous values"""
    form = GammaForm()
    for field in form:
        field.data = getattr(instance, field.name)
    return form

def send_email(user):
    from flask.ext.mail import Mail, Message
    mail = Mail(app)
    msg = Message("Gamma Computations Complete",
                  recipients=[user.email])
    msg.body = """A simulation has been completed by the Flask Gamma app. Please log in at

http://localhost:5000/login

to see the results.

---
This email has been automatically generated by the Gamma app created by
Parampool. If you don't want email notifications when a result is found, please
register a new user and leave the 'notify' field unchecked."""
    mail.send(msg)

@app.route('/reg', methods=['GET', 'POST'])
def create_login():
    from forms import register_form
    form = register_form(request.form)
    if request.method == 'POST' and form.validate():
        user = User()
        form.populate_obj(user)
        user.set_password(form.password.data)

        db.session.add(user)
        db.session.commit()

        login_user(user)
        return redirect(url_for('index'))
    return render_template("reg.html", form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    from forms import login_form
    form = login_form(request.form)
    if request.method == 'POST' and form.validate():
        user = form.get_user()
        login_user(user)
        return redirect(url_for('index'))
    return render_template("login.html", form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/old')
@login_required
def old():
    data = []
    user = current_user
    if user.is_authenticated():
        instances = user.Gamma.order_by('-id').all()
        for instance in instances:
            form = populate_form_from_instance(instance)

            result = instance.result
            if instance.comments:
                result += "<h3>Comments</h3>" + instance.comments
            data.append({'form':form, 'result':result, 'id':instance.id})

    return render_template("old.html", data=data)

@app.route('/add_comment', methods=['GET', 'POST'])
@login_required
def add_comment():
    user = current_user
    if request.method == 'POST' and user.is_authenticated():
        instance = user.Gamma.order_by('-id').first()
        instance.comments = request.form.get("comments", None)
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/delete/<id>', methods=['GET', 'POST'])
@login_required
def delete_post(id):
    id = int(id)
    user = current_user
    if user.is_authenticated():
        if id == -1:
            instances = user.Gamma.delete()
        else:
            try:
                instance = user.Gamma.filter_by(id=id).first()
                db.session.delete(instance)
            except:
                pass

        db.session.commit()
    return redirect(url_for('old'))


if __name__ == '__main__':
    if not os.path.isfile(os.path.join(os.path.dirname(__file__), 'sqlite.db')):
        db.create_all()
    app.run(debug=True)
