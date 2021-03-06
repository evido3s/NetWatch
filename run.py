from netwatch import app, db
from netwatch.models import *
from netwatch.routes import *
from netwatch.secrets import *
from netwatch import poller


db.create_tables([Rule, Node, NodeRule, Settings, ConnectionProfile, Config, Log],
                 safe=True)

add_settings(app.config['DUMMY_DATA'])

poller.poller_init()

if __name__ == '__main__':
    app.run(host='0.0.0.0')
