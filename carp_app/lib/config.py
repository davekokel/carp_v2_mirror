from carp_app.lib.secret import db_url, get_secret
from carp_app.lib.db import get_engine
DB_URL = db_url()
engine = get_engine
