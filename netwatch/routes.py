from flask import render_template, redirect, url_for, flash, request
from netwatch import app, models, forms
from socket import gethostname
import datetime
import psutil


@app.route('/')
def home():

    node_list = models.list_all_nodes()
    rule_list = models.list_all_rules()
    node_table = models.dict_node_table()

    number_node_online = len(models.list_online_nodes())

    number_total_nodes = len(node_list)
    number_total_rules = len(rule_list)
    number_total_node_rules = len(models.list_all_node_rules())

    number_comp_rules = len(models.list_compliant_noderules())
    number_pend_rules = len(models.list_pending_noderules())
    number_fail_rules = len(models.list_noncompliant_noderules())

    number_totally_comp_nodes = len(models.list_compliant_nodes())

    percent_comp_rules = models.percent_calc(number_total_node_rules, number_comp_rules)
    percent_fail_rules = models.percent_calc(number_total_node_rules, number_fail_rules)

    percent_totally_comp_nodes = models.percent_calc(number_total_nodes, number_totally_comp_nodes)
    percent_pend_nodes = 0  # Not yet in use on Compliance by kit pie chart...
    percent_not_totally_comp_nodes = int(100 - percent_totally_comp_nodes)

    percent_online_nodes = models.percent_calc(number_total_nodes, number_node_online)
    percent_offline_nodes = int(100 - percent_online_nodes)

    number_config_backups = models.number_files_in_dir('./configs/', '.cfg')
    number_logs = models.number_files_in_dir('./logs/', '.log')

    boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
    uptime = datetime.datetime.now() - boot_time
    pretty_uptime = "{}d {}h {}m {}s".format(uptime.days,
                                                    uptime.seconds // 3600,
                                                    (uptime.seconds // 60) % 60,
                                                    uptime.seconds % 60)

    return render_template('index.html',
                           title='Dashboard',
                           node_table=node_table,
                           node_list=node_list,
                           rule_list=rule_list,
                           number_total_nodes=number_total_nodes,
                           number_node_online=number_node_online,
                           number_comp_rules=number_comp_rules,
                           number_pend_rules=number_pend_rules,
                           number_fail_rules=number_fail_rules,
                           percent_comp_rules=percent_comp_rules,
                           percent_fail_rules=percent_fail_rules,
                           percent_totally_comp_nodes=percent_totally_comp_nodes,
                           percent_pend_nodes=percent_pend_nodes,
                           percent_not_totally_comp_nodes=percent_not_totally_comp_nodes,
                           percent_online_nodes=percent_online_nodes,
                           percent_offline_nodes=percent_offline_nodes,
                           refresh_rate=models.get_settings("dash_refresh_rate_secs"),
                           last_poll=models.get_settings("last_poll"),
                           number_config_backups=number_config_backups,
                           number_logs=number_logs,
                           app_srv_hostname=gethostname(),
                           uptime=pretty_uptime
                           )


@app.route('/new')
def tbc():

    # Placeholder page

    return render_template('BLANK.html',
                           title='Coming Soon')


@app.route('/rules/', defaults={'model': 'rules'})
@app.route('/nodes/', defaults={'model': 'nodes'})
@app.route('/connectionprofiles/', defaults={'model': 'connectionprofiles'})
def modeltable(model):
    if model == "nodes":
        title = 'Nodes'
        columns = models.list_columns_for("Node")
        rows = models.list_all_nodes()
    elif model == "rules":
        title = 'Rules'
        columns = models.list_columns_for("Rule")
        rows = models.list_all_rules()
    elif model == "connectionprofiles":
        title = 'Connection Profiles'
        columns = models.list_columns_for("ConnectionProfile")
        rows = models.list_all_connectionprofiles()

    return render_template('modeltable.html',
                           columns=columns,
                           rows=rows,
                           slug=model,
                           title=title
                           )


@app.route("/<slug>/new/", methods=('GET', 'POST'))
def new_model(slug):
    '''
    Create new node
    '''
    if slug == "nodes":
        title = "Node"
        form = forms.NodeForm()
        if form.validate_on_submit():
            # Get form:
            node_name = form.node_name.data
            ip_address = form.ip_address.data
            # Save in database:
            try:
                result = models.create_node(node_name, ip_address)
                flash(*result)
                return redirect(url_for('modeltable', model=slug))
            except:
                flash(*result)
    if slug == "connectionprofiles":
        title = "Connection Profile"
        form = forms.ConnectionProfileForm()
        if form.validate_on_submit():
            # Get form:
            profile_dict = {'profile_name': form.profile_name.data,
                            'device_os': form.device_os.data,
                            'ssh_username': form.ssh_username.data,
                            'ssh_password': form.ssh_password.data,
                            'ssh_enable': form.ssh_enable.data,
                            'config_command': form.config_command.data}
            # Save in database:
            result = models.create_connectionprofile(profile_dict)
            flash(*result)
            return redirect(url_for('modeltable', model='connectionprofiles'))

    if slug == "rules":
        title = "Rule"
        form = forms.RuleForm()
        if form.validate_on_submit():
            # Get form:
            if form.found_in_config.data == 'False':
                form.found_in_config.data = bool(False)
            rule_dict = {'rule_name': form.rule_name.data,
                         'rule_desc': form.rule_desc.data,
                         'config': form.config.data,
                         'regex': form.regex.data,
                         'found_in_config': form.found_in_config.data,
                         'remediation_config': form.remediation_config.data}
            # Save in database:
            result = models.create_rule(rule_dict)
            flash(*result)
            return redirect(url_for('modeltable', model='rules'))

    return render_template('new_model.html',
                           title='New ' + title,
                           slug=slug,
                           form=form
                           )


@app.route("/<slug>/edit/<id>", methods=('GET', 'POST'))
def edit_model(slug, id):
    if slug == "nodes":
        my_model = models.get_node(id)
        form = forms.NodeForm(obj=my_model)

        if form.validate_on_submit():
            form.populate_obj(my_model)
            try:
                result = models.update_node(my_model)
                flash(*result)
                return redirect(url_for('modeltable', model=slug))
            except:
                flash(*result)

    if slug == "rules":
        my_model = models.get_rule(id)
        form = forms.RuleForm(obj=my_model)

        if form.validate_on_submit():
            form.populate_obj(my_model)
            if my_model.found_in_config == 'False':
                my_model.found_in_config = bool(False)
            try:
                result = models.update_rule(my_model)
                flash(*result)
                return redirect(url_for('modeltable', model=slug))
            except:
                pass

    if slug == "connectionprofiles":
        my_model = models.get_connectionprofile(id)
        form = forms.ConnectionProfileForm(obj=my_model)

        if form.validate_on_submit():
            form.populate_obj(my_model)
            try:
                result = models.update_connectionprofile(my_model)
                flash(*result)
                return redirect(url_for('modeltable', model=slug))
            except:
                pass

    return render_template(
        'edit_model.html',
        title='Edit ' + slug,
        form=form,
        my_model=my_model)


@app.route("/<slug>/delete", methods=('POST',))
def delete_model(slug):
    if slug == "nodes":
        try:
            result = models.delete_node(id=request.form['id'])
            flash(*result)
        except:
            flash(*result)
        return redirect(url_for('modeltable', model='nodes'))

    if slug == "connectionprofiles":
        try:
            result = models.delete_connectionprofile(profile_id=request.form['id'])
            flash(*result)
        except:
            flash(*result)
        return redirect(url_for('modeltable', model='connectionprofiles'))


# Error page routes
@app.errorhandler(404)  # page not found (incorrect URL)
@app.errorhandler(405)  # method not allowed (no PUT etc.)
@app.errorhandler(500)  # internal server error (code/server error)
def http_error(e):
    return render_template('error.html',
                           title=e,
                           err_message=e), e.code