from influxdb_client import InfluxDBClient

import psycopg2
from psycopg2 import sql

import urllib.request
import time

# ------------ CONSTANTS AND SETUP ----------------------------------
from mysecrets import *
from mynumbers import *
from mynumbers_ret45d import *
from mycontacts import *
from myswitches import *
from mystrings import *
from mynumbers_combined import *

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
            print(f"Executing: {s}")
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

    print(f"Calling url: {url}");

    if addgroup:
        req = urllib.request.Request(url, method='PUT')
    else:
        req = urllib.request.Request(url, method='DELETE')

    authorization_header = "Bearer " + openhabAPI_token
    req.add_header("Authorization", authorization_header)
    req.add_header("Content-Type","text/plain")

    with urllib.request.urlopen(req) as response:
        status = response.status
        content = response.read()

        write_to_file(output_file,f"Status Code: {status}")


def create_postgresql_table(measurement):
    # Ensure that openHAB creates the Hypertable
    write_to_file(output_file,f"Ensuring hypertable exists for measurement {measurement}...")
    print(f"Adding {measurement} to 'persist_jdbc_everysecond' group for creation of hypertable.")
    openhab_rest_api(measurement,"persist_jdbc_everysecond",True)
    print("Sleeping for 5s to allow openHAB to create the hypertable")
    time.sleep(5)
    print(f"Removing {measurement} from 'persist_jdbc_everysecond' group after creation of hypertable.")
    openhab_rest_api(measurement,"persist_jdbc_everysecond",False)



def migrate_measurement(flux,measurement):
    write_to_file(output_file,f"Exporting influxDB measurement {measurement} to postgresql...")
    flux = flux.replace("<measurement>", measurement)
    influx.query_api().query(flux)

    # Ensure that openHAB creates the Hypertable
    create_postgresql_table(measurement)

    # Migrate the measurement using SQL statements
    # a. Delete any rows in the openHAB created table by the 'everysecond' persistance
    # b. Enable compression on the openHAB created hypertable.
    # c. Insert all Influxdata items into the Hypertable
    # d. Drop the _old table
    # e. Manualy compress the hypertable
    # f. Set a default compression policy on the hypertable
    sql_statements = [
      "DELETE FROM \"<measurement>\";",
      "ALTER TABLE \"<measurement>\" SET (timescaledb.compress=true);",
      "INSERT INTO \"<measurement>\" (time, value) SELECT time::timestamp without time zone AT TIME ZONE '<influx_tz>', value FROM \"<measurement>_old\" ORDER BY time ASC;",
      "DROP TABLE \"<measurement>_old\";",
      "SELECT compress_chunk(i, if_not_compressed => true) FROM show_chunks('\"<measurement>\"',   now()::timestamp - INTERVAL '1 week', now()::timestamp - INTERVAL '5 years'  ) i;",
      "SELECT add_compression_policy('\"<measurement>\"', INTERVAL '7 days', if_not_exists => true);",
    ]

    for idx, item in enumerate(sql_statements):
        sql_statements[idx] = item.replace("<measurement>", measurement)
        sql_statements[idx] = sql_statements[idx].replace("<influx_tz>", influxdb_timezone)

    return run_sql_statements(output_file,sql_statements)



def addRetentionPolicy(measurement, retentionpolicy):
    sql_statements = [
      "SELECT add_retention_policy('\"<measurement>\"', INTERVAL '<retentionpolicy>', if_not_exists => true);",
    ]

    for idx, item in enumerate(sql_statements):
        sql_statements[idx] = item.replace("<measurement>", measurement)
        sql_statements[idx] = sql_statements[idx].replace("<retentionpolicy>", retentionpolicy)

    return run_sql_statements(output_file,sql_statements)



def getBaseFlux(range_start, mapping):
    flux = '''
    import "sql"

    from(bucket: "oh_bucket")
    |> range(start: <range_start>)
    |> filter(fn: (r) => r["_measurement"] == "<measurement>")
    |> keep(columns: ["_time", "_value"])
    |> map(fn: (r) => ({r with value: <mapping>, }))
    |> drop(columns: ["_value"])
    |> rename(columns: {_time:"time"})
    |> sql.to(
            driverName: "postgres",
            dataSourceName: "postgresql://<username>:<password>@<host>:<port>/<dbname>",
            table: "<measurement>_old",
    )

    '''
    flux = flux.replace("<range_start>", range_start)
    flux = flux.replace("<mapping>", mapping)
    flux = flux.replace("<username>", timescale_db_user)
    flux = flux.replace("<password>", timescale_db_password)
    flux = flux.replace("<host>", timescale_db_host)
    flux = flux.replace("<port>", str(timescale_db_port))
    flux = flux.replace("<dbname>", timescale_db_name)

    return flux


# ------------------------------------- SWITCHES ----------------------------------------

# 2. Generate and run export Flux for each measurement, the measurement will be written to the new postgress database with an "_old" postfix.
if len(switches) > 0:
    write_to_file(output_file,"\n\n--- Migrating Switches ---\n")
    flux = getBaseFlux("0", "if r._value >= 1 then \"ON\" else \"OFF\"")

    for m in switches:

    # Migrate the measurement
        error_occured = migrate_measurement(flux, m)

        if error_occured:
            continue

    # Add the item to the everyChange persistance
        openhab_rest_api(m,"persist_jdbc_everyupdate",True)

# ------------------------------------- NUMBERS 45d retention ----------------------------------------

if len(numbers_45d) > 0:
    write_to_file(output_file,"\n\n--- Migrating Numbers with 45d retention policy ---\n")
    flux = getBaseFlux(numbers45d_influx_range, "r._value")
    for m in numbers_45d:

    # Migrate the measurement
        error_occured = migrate_measurement(flux, m)
        if error_occured:
            continue

    # Add retention policy
        error_occured = addRetentionPolicy(m,numbers45d_psql_retention_policy)
        if error_occured:
            continue

    # Add the item to the everyChange persistance
        openhab_rest_api(m,"persist_jdbc_everychange",True)

# ------------------------------------- NUMBERS -----------------------------------

if len(numbers) > 0:
    write_to_file(output_file,"\n\n--- Migrating Numbers ---\n")
    flux = getBaseFlux("0", "r._value")

    for m in numbers:
        # Migrate the measurement
        error_occured = migrate_measurement(flux,m)

        if error_occured:
            continue

        # Add the item to the everyChange persistance
        openhab_rest_api(m,"persist_jdbc_everychange",True)

# ------------------------------------- CONTACTS ----------------------------------------

if len(contacts) > 0:
    write_to_file(output_file,"\n\n--- Migrating Contacts ---\n")
    flux = getBaseFlux("0", "if r._value >= 1 then \"OPEN\" else \"CLOSED\"")

    for m in contacts:
        # Migrate the measurement
        error_occured = migrate_measurement(flux,m)

        if error_occured:
            continue

        # Add the item to the everyChange persistance
        openhab_rest_api(m,"persist_jdbc_everyupdate",True)

# ------------------------------------- STRINGS ----------------------------------------

if len(strings) > 0:
    write_to_file(output_file,"\n\n--- Migrating Strings ---\n")
    flux = getBaseFlux(strings_influx_range, "r._value")

    for m in strings:
    # Migrate the measurement
        error_occured = migrate_measurement(flux,m)
        if error_occured:
            continue

    # Add retention policy
        error_occured = addRetentionPolicy(m,string_retention_policy)
        if error_occured:
            continue

        # Add the item to the everyChange persistance
        openhab_rest_api(m,"persist_jdbc_everychange",True)
        openhab_rest_api(m,"persist_jdbc_everyday",True)

# ------------------------------------- COMBINED NUMBER ITEMS ----------------------------------------

if len(numbers_combined) > 0:

    write_to_file(output_file,"\n\n--- Migrating Combined Numbers ---\n")
    for m in numbers_combined:
        # Retrieve the real measurement and item names from the configuration file.
        measurement = m[1];
        influx_table = m[0];

        # Replace the filter in the flux schema to get the correct measurement and item
        flux = getBaseFlux("0", "r._value");

        #Original filter:       |> filter(fn: (r) => r["_measurement"] == "<measurement>")
        #New filter     :       |> filter(fn: (r) => r["_measurement"] == "<influx_table>" and r.item == "<measurement>")

        # Replace the first occurance of '<measurement>' in the flux with the correct influx_table and the item filter
        flux=flux.replace("<measurement>", influx_table + "\" and r.item == \"<measurement>", 1)

        # Migrate the measurement
        error_occured = migrate_measurement(flux, measurement)

        if error_occured:
            continue

        # Add the item to the everyChange persistance
        openhab_rest_api(measurement,"persist_jdbc_everychange",True)


# Close the output file
output_file.close()