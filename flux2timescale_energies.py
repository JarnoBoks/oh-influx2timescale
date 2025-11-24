from influxdb_client import InfluxDBClient

import psycopg2
from psycopg2 import sql

import urllib.request
import time

# Preconditions:
# - The script expects that the influxDB v2 database has measurements with the openHAB data in it, the measurements should have the name of the openHAB item.
# - The script expects that the TimescaleDB database is empty before starting the migration.
# - TimescaleDB is installed and configured correctly for the database openhab_db
# - The openHAB JDBC persistance is setup and working correctly with TimescaleDB, the database should be emtpy before starting the migration
# - The openHAB JDBC persistance strategy "everysecond" is configured and working correctly and is applied for items in the "persist_jdbc_everysecond" group
# - The openHAB JDBC persistance strategy "everyupdate" is configured and working correctly and is applied for items in the "persist_jdbc_everyupdate" group
# - The openHAB JDBC persistance strategy "everychange" is configured and working correctly and is applied for items in the "persist_jdbc_everychange" group
# - The InfluxDB database oh_bucket is accessible and contains the data to be migrated
# - The InfluxDBClient library is installed: pip install influxdb-client
# - The psycopg2 library is installed: pip install psycopg2

# Tips/trics:
# - See the documentation of the JDBC persistance for openHAB to clean up links from items to none existing tables:
#   https://www.openhab.org/addons/persistence/jdbc/#maintenance

# Behaviour:
# - For each item in the switches, numbers and contacts lists:
#   1. An export Flux query is generated and executed that exports all data for that item from InfluxDB to a new table in TimescaleDB with the same name as the item but with an "_old" postfix.
#   2. The openHAB REST API is called to add the item to the "persist_jdbc_everysecond" group so openHAB creates the hypertable for that item.
#   3. The following SQL statements are executed for the item:
#      a. Delete any rows in the openHAB created table that are persisted by the 'everysecond' persistance
#      b. Enable compression on the openHAB created hypertable.
#      c. Insert all Influxdata items into the Hypertable
#      d. Drop the _old table
#      e. Manually compress the hypertable
#      f. Set a default compression policy on the hypertable
#   4. The openHAB REST API is called to add the item to the "persist_jdbc_everyupdate" group (for switches and contacts) or the "persist_jdbc_everychange" group (for numbers) so
#      openHAB persists any new updates to the item.


# SETUP SECTION
# ------------------------------------------------------------------
# Secrets and connection details
#
# Rename the file secrets_format.py to secrets.py and fill in your own connection details before running this script.
# Paste your openHAB item list in the switches, numbers and contacts lists below. You can use an openHAB script that exports all items of a certain type to get the list.
# fe. the following javascript script will export all Switch items:
#   var txt='';
#   items.getItems().filter((i) => (i.type == "Switch"))
#                     .forEach((i) => {
#                         txt = txt + '"' + i.name + '",';
#   })
#
#   console.log("SWITCHES:");
#   console.log(txt);

energies = [
    "Gridmeter_PowerFeedin",
    "SolaredgeInverter_Production"  ,
]


# ------------ CONSTANTS AND SETUP ----------------------------------
# Import connection details & passwords from myscrets.py
from mysecrets import *

# Setup InfluxDB client
influx = InfluxDBClient(url=influxdb_url, token=influxdb_token, org=influxdb_org, timeout=400000)

# Setup the Output file
output_file_path = "flux2timescale_output"

from datetime import datetime
current_datetime = datetime.now().strftime("%Y-%m-%d_%H_%M_%S")
print(current_datetime)
output_file_path = output_file_path + "_" + current_datetime + ".log"
import os
if os.path.exists(output_file_path):
  os.remove(output_file_path)

output_file = open(output_file_path, "x")

# ---------------------------------------------------------------------------   FUNCTIONS

# Write to file and print to console
def write_to_file(f,x):
    f.write(x)
    f.write("\n")
    print(x);

# Run a list of SQL statements
def run_sql_statements(fle, statements):
    err = False
    # Database connection settings
    conn_info = {
        "host": timescale_db_host,
        "port": timescale_db_port,
        "dbname": timescale_db_name,
        "user": timescale_db_user,
        "password": timescale_db_password
    }

    try:
        # Connect to PostgreSQL
        conn = psycopg2.connect(**conn_info)
        conn.autocommit = False  # you control commits
        cur = conn.cursor()

        for s in statements:
            write_to_file(fle, f"Executing: {s}")
            cur.execute(s)

        conn.commit()
        write_to_file(fle,"All statements executed successfully!")

    except Exception as e:
        conn.rollback()
        write_to_file(fle,"Error occurred, rolled back.")
        write_to_file(fle,str(e))
        err = True

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
        return err

# Call the openHAB REST API to add or remove an item from a group
def openhab_rest_api(item, group, addgroup):
    url=f"https://openhab.lan.ratatosk.nl/rest/items/{group}/members/{item}"

    write_to_file(output_file,f"Calling url: {url}");

    if addgroup:
        req = urllib.request.Request(url, method='PUT')
    else:
        req = urllib.request.Request(url, method='DELETE')

    req.add_header("Authorization", "Bearer oh.VisualStudioCode.Q612eT3gvoCVBeb23s6RKmIqmZMr4SSznlbHiK1YS6JGG7haMYgBN64R6FMhPK9RzzAGI5t1uzKjMYMenOg")
    req.add_header("Content-Type","text/plain")

    with urllib.request.urlopen(req) as response:
        status = response.status
        content = response.read()

        write_to_file(output_file,f"Status Code: {status}")
        write_to_file(output_file,f"Content Length: {len(content)} bytes")
        write_to_file(output_file,f"\nFirst 500 characters of response:\n{content.decode('utf-8')[:500]}")

def setup_flux(source_flux, measurement):
    schema = source_flux.replace("<measurement>", measurement)
    schema = schema.replace("<username>", timescale_db_user)
    schema = schema.replace("<password>", timescale_db_password)
    schema = schema.replace("<host>", timescale_db_host)
    schema = schema.replace("<port>", str(timescale_db_port))
    schema = schema.replace("<dbname>", timescale_db_name)
    return schema

def setup_table(measurement):
# Ensure that openHAB creates the Hypertable
    write_to_file(output_file,f"Adding {measurement} to 'persist_jdbc_everysecond' group for creation of hypertable.")
    openhab_rest_api(measurement,"persist_jdbc_everysecond",True)
    print("Sleeping for 10s so openHab can create the hypertable")
    time.sleep(10)
    write_to_file(output_file,f"Removing {measurement} from 'persist_jdbc_everysecond' group after creation of hypertable.")
    openhab_rest_api(measurement,"persist_jdbc_everysecond",False)


def migrate_measurement(measurement):
    flux = setup_flux(schema,measurement)
    write_to_file(output_file,f"Exporting measurement {measurement}...")
    influx.query_api().query(flux)

# Ensure that openHAB creates the Hypertable
    setup_table(measurement)

# Migrate the measurement

# a. Delete any rows in the openHAB created table by the 'everysecond' persistance
# b. Enable compression on the openHAB created hypertable.
# c. Insert all Influxdata items into the Hypertable
# d. Drop the _old table
# e. Manualy compress the hypertable
# f. Set a default compression policy on the hypertable
    sql_statements = [
      "DELETE FROM \"<measurement>\";",
      "ALTER TABLE \"<measurement>\" SET (timescaledb.compress=true);",
      "INSERT INTO \"<measurement>\" SELECT * FROM \"<measurement>_old\";",
      "DROP TABLE \"<measurement>_old\";",
      "SELECT compress_chunk(i, if_not_compressed => true) FROM show_chunks('\"<measurement>\"',   now()::timestamp - INTERVAL '1 week', now()::timestamp - INTERVAL '5 years'  ) i;",
      "SELECT add_compression_policy('\"<measurement>\"', INTERVAL '7 days', if_not_exists => true);",
    ]

    for idx, item in enumerate(sql_statements):
        sql_statements[idx] = item.replace("<measurement>", measurement)

    return run_sql_statements(output_file,sql_statements)

# ---------------------------------------------------------------------------   SWITCHES

# 2. Generate and run export Flux for each measurement, the measurement will be written to the new postgress database with an "_old" postfix.
for m in energies:

    schema = '''
import "sql"

from(bucket: "oh_bucket")
  |> range(start: 0)
  |> filter(fn: (r) => r["_measurement"] == "Energy" and r.item == "<measurement>")
  |> keep(columns: ["_time", "_value"])
  |> map(fn: (r) => ({r with value: r._value, })
        )  |> drop(columns: ["_value"])
  |> rename(columns: {_time:"time"})
  |> sql.to(
        driverName: "postgres",
        dataSourceName: "postgresql://<username>:<password>@<host>:<port>/<dbname>",
        table: "<measurement>_old",
  )

'''

# Migrate the measurement
    error_occured = migrate_measurement(m)

    if error_occured:
        continue

# Add the item to the everyChange persistance
    openhab_rest_api(m,"persist_jdbc_everyupdate",True)


# Close the output file
output_file.close()