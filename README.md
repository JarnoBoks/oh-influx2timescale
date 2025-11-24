# openHAB - Migrate influxDB v2 to Timescale DB


:::info
## This script comes without any warranty. It may or may not function in your specific situation.

## Please note that executing the script can lead to data loss. Allways backup your data!

:::

## Purpose

* Migrate openHAB data from an influxDB v2 database to a TimescaleDB database
* The script uses the InfluxDB Flux "sql.to" function to export data from InfluxDB to TimescaleDB
* The script also uses the openHAB REST API to add items to the correct persistance groups so openHAB creates the hypertables
* The script enables compression on the hypertables and sets a default compression policy
* The script assumes that the InfluxDB measurements have the same name as the openHAB items

## Usage

* Rename the sample files **mycontacts.sample.py**, **mynumbers.sample.py**, **mystrings.sample.py** and **myswitches.sample.py** to mycontacts.py, mynumbers.py, mystrings.py and myswitches.py and paste your own items in them.
* Rename the file **mysecrets.sample.py** to mysecrets.py and fill in your own connection details before running this script.
* Run the script:

  `python flux2timescale.py`


:::warning
## !! Any pre-existing data in the TimescaleDB for items that are migrated will be deleted !!

:::

## Pre-conditions

* The script expects that the influxDB v2 database has measurements with the openHAB data in it, the measurements should have the name of the openHAB item.
* TimescaleDB is installed and configured correctly for the database openhab_db
* The openHAB JDBC persistance is setup and working correctly with TimescaleDB, the database should be emtpy before starting the migration
* The openHAB JDBC persistance strategy "everysecond" is configured and working correctly and is applied for items in the `persist_jdbc_everysecond` group
* The openHAB JDBC persistance strategy "everyupdate" is configured and working correctly and is applied for items in the `persist_jdbc_everyupdate` group
* The openHAB JDBC persistance strategy "everychange" is configured and working correctly and is applied for items in the `persist_jdbc_everychange` group
* The InfluxDB database oh_bucket is accessible and contains the data to be migrated
* The InfluxDBClient library is installed:

  `pip install influxdb-client`
* The psycopg2 library is installed:

  `pip install psycopg2`

## Script behaviour

For each item in the switches, numbers and contacts lists:


1. An export Flux query is generated and executed that exports all data for that item from InfluxDB to a new table in TimescaleDB with the same name as the item but with an "_old" postfix.
2. The openHAB REST API is called to add the item to the "persist_jdbc_everysecond" group.
3. OpenHAB will create the hypertable (if it doesn’t exist) and will put some data in the table. That data (an any other pre-existing data will be removed in the next step. After 10 seconds, the script will remove the item from the ‘persist_jdbc_everysecond’ group.
4. The following SQL statements are executed for the item:

   a. Delete any rows in the openHAB created table that are persisted by the 'everysecond' persistance stratget

   b. Enable compression on the openHAB created hypertable.

   c. Insert all Influxdata items into the Hypertable

   d. Drop the _old table

   e. Manually compress the hypertable

   f. Set a default compression policy on the hypertable

   g. *For string items*: set a default retention policy of 7 days on the string hypertable. (this is configurable in mysecrets.py)
5. The openHAB REST API is called to add the item to the *persist_jdbc_everyupdate*-group (for switches and contacts) or the *persist_jdbc_everychange*-group (for numbers and strings) so openHAB will persist any new updates/changes to the item.
6. *For string items*: If a string isn’t updated at least once a week there is a risk that the retention policy will leave openHAB with an empty table for strings. To prevent this from happening, string items will be added to the *persist_jdbc_everyday*-group as well.

   \

The script will write its output to stdout and in to a logfile in the same folder as the script. Check the logfile for any errors.

## Additional information:

* By default the script exports all pre-existing Influxdata to TimescaleDB. I had one table that was to big to be exported from InfluxDB (received timeouts). You can change the amount of data that will be exported by changing the ‘range’ items in the schema-flux.
* See the documentation of the JDBC persistance for openHAB to clean up links from items to none existing tables at https://www.openhab.org/addons/persistence/jdbc/#maintenance
* In order to let the script function, the JDBC persistancestrategy is setup with this yaml.

  **Note**: you have to create the item groups (persist_jdbc_xxx) yourself!

  ```yaml
  configurations:
    - items:
        - persist_jdbc_everychange*
      strategies:
        - everyChange
      filters:
        - excludeEmpty
    - items:
        - persist_jdbc_everysecond*
      strategies:
        - everySecond
      filters: []
    - items:
        - persist_jdbc_everyupdate*
      strategies:
        - everyUpdate
      filters:
        - excludeEmpty
    - items:
        - persist_jdbc_everyday*
      strategies:
        - everyDay
      filters:
        - excludeEmpty
  aliases: {}
  cronStrategies:
    - name: everySecond
      cronExpression: "* * * * * ? *"
    - name: everyHour
      cronExpression: 0 0 * * * ? *
    - name: everyDay
      cronExpression: 0 0 0 * * ? *
  defaultStrategies: []
  thresholdFilters: []
  timeFilters: []
  equalsFilters:
    - name: excludeEmpty
      values:
        - "NULL"
        - UNDEF
      inverted: true
  includeFilters: []

  ```
* You can use a Javascript like this, to create a list of all switchtitems in your openHAB installation. Change the second line to Number or Contact for the other types.

```javascript
var txt='';
items.getItems().filter((i) => (i.type == "Switch"))
                .forEach((i) => {
                  txt = txt + '"' + i.name + '",';
            })
console.log("SWITCHES:");
console.log(txt);
```


