# pyright: reportIncompatibleVariableOverride=false

from peewee import (
    SQL,
    BigIntegerField,
    BlobField,
    BooleanField,
    CharField,
    DateTimeField,
    DecimalField,
    ForeignKeyField,
    IntegerField,
    Model,
    PostgresqlDatabase,
    SmallIntegerField,
    TextField,
)
from playhouse.postgres_ext import ArrayField  # pyright: ignore[reportMissingTypeStubs]

from minibrain.context import Context

context = Context.get()

database = PostgresqlDatabase(
    context.mb_dbname,
    user=context.mb_dbuser,
    password=context.mb_dbpass,
    host=context.mb_dbhost,
)


class BaseModel(Model):
    class Meta:
        database = database


class Country(BaseModel):
    code = CharField()
    name = CharField()

    class Meta:
        table_name = "country"


class Filearr(BaseModel):
    path = CharField(unique=True)
    mirrors = ArrayField(field_class=SmallIntegerField, null=True)

    class Meta:
        table_name = "filearr"


class Hash(BaseModel):
    file = ForeignKeyField(
        column_name="file_id", field="id", model=Filearr, primary_key=True
    )
    mtime = IntegerField()
    size = BigIntegerField()
    md5 = BlobField()
    sha1 = BlobField()
    sha256 = BlobField()
    sha1piecesize = IntegerField()
    sha1pieces = BlobField()
    btih = BlobField()
    pgp = TextField()
    zblocksize = SmallIntegerField()
    zhashlens = CharField(null=True)
    zsums = BlobField()

    class Meta:
        table_name = "hash"


class Marker(BaseModel):
    subtree_name = CharField()
    markers = CharField()

    class Meta:
        table_name = "marker"


class Region(BaseModel):
    code = CharField()
    name = CharField()

    class Meta:
        table_name = "region"


class Server(BaseModel):
    identifier = CharField(unique=True)
    baseurl = CharField()
    baseurl_ftp = CharField()
    baseurl_rsync = CharField()
    enabled = BooleanField()
    status_baseurl = BooleanField()
    region = CharField()
    country = CharField()
    asn = IntegerField()
    prefix = CharField()
    ipv6_only = BooleanField(constraints=[SQL("DEFAULT false")])
    score = SmallIntegerField()
    scan_fpm = IntegerField()
    last_scan = DateTimeField(null=True)
    comment = TextField()
    operator_name = CharField()
    operator_url = CharField()
    public_notes = CharField()
    admin = CharField()
    admin_email = CharField()
    lat = DecimalField(null=True)
    lng = DecimalField(null=True)
    country_only = BooleanField()
    region_only = BooleanField()
    as_only = BooleanField()
    prefix_only = BooleanField()
    other_countries = CharField()
    file_maxsize = IntegerField(constraints=[SQL("DEFAULT 0")])

    class Meta:
        table_name = "server"
        indexes = ((("enabled", "status_baseurl", "score"), False),)


class Version(BaseModel):
    component = TextField()
    major = IntegerField()
    minor = IntegerField()
    patchlevel = IntegerField()

    class Meta:
        table_name = "version"
