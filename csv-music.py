"""csv-music
A raspberry pi focused, .csv driven, audio signal scheduler.
Intent is to schedule .mp3 audible signals through the day.
And to schedule based on a school schedule.

Ideally, if the school schedule changes qualitatively, 
e.g. the school implements drop-4 scheduling,
the program can be reconfigured by revising the .csv files
with the school calendar and bell schedule without revising
the script.

Requires: python 3.6+, crontab, sqlite3, virtual environment
pi should have: vlc installed, music downloaded, python3.6+,
also, main directory should have a virtual environment called venv
"""

import argparse, csv, sqlite3, yaml
from crontab import CronTab
from datetime import datetime as dt
from datetime import timedelta
from time import strptime
from typing import OrderedDict
from pathlib import Path

YAML = "csv-music.yaml"


def csv_to_sql(fname: Path, cur: sqlite3.Cursor, table: str):
    """move csv file to sql dbase
    Parameters
    ----------
        fname : Path to .csv file
        con : connection object
        table : table name
    Returns:
    --------
        n : number of rows read
    """
    #   local helper functions
    def ctime(text: str):
        """throw error if text is not a time"""
        return strptime(text, "%H:%M")

    def cdate(text: str):
        """throw error if text is not a date"""
        return strptime(text, "%m:%D:%Y")

    def def_ok(x):
        return True

    SQLtypes = OrderedDict(
        {"INTEGER": int, "REAL": float, "DATE": cdate, "TIME": ctime, "TEXT": def_ok}
    )

    cur.execute(
        f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table};'"
    )
    texists = cur.fetchone()
    n = 0
    with open(fname, "r") as f:
        r = csv.DictReader(f)
        for row in r:
            if not texists:
                create_command = f"CREATE TABLE {table} ("
                dtypes = {}
                for k in r.fieldnames:
                    for Dt, f in SQLtypes.items():
                        try:
                            vout = f(row[k])
                            break
                        except ValueError:
                            pass
                    dtypes[k] = Dt
                    create_command += f"{k}  {Dt}, "
                create_command = create_command[0:-2] + ");"
                cur.execute(create_command)
                db_result = cur.fetchall()
                texists = True
            break

    with open(fname, "r") as f:
        r = csv.DictReader(f)
        data_out = [(row) for row in r]

    for d in data_out:
        insertCommand = f"""INSERT INTO {table} ({', '.join(r.fieldnames)}) VALUES ("{'","'.join([d[v] for v in r.fieldnames])}");"""
        cur.executescript(insertCommand)

    return len(data_out)


class SchedDB:
    """Manages database and queries
    initialize with the name of the yaml file (relative path) and an active cursor to the
    scheduling database
    """

    def __init__(self, f_yaml: str, cur: sqlite3.Cursor):
        self.cursor = cur
        y = yaml.safe_load_all(
            Path(Path(__file__).parent.resolve(), f_yaml).read_text()
        ).__next__()
        self.dir = Path(Path(__file__).parent.resolve(), y["directory"])
        self.music_dir = y["music"]
        self.files = y["objects"]
        self.script = y["merge"]
        for t, f in self.files.items():
            n = csv_to_sql(Path(self.dir, f), cur, t)
            print(f"{t} has {n} rows")

    def list(self):
        """
        handy method to show user what teachers, classrooms, and bell schedules are available
        """
        print(f"{__file__}:\nSchedules are in {self.dir}")
        # query tuples are (column heading, table, printed label)
        qvs = [
            ("teacher", "teachers", "teacher"),
            ("schedule", "bells", "Bell schedule"),
            ("room", "teachers", "room"),
        ]
        for qv in qvs:
            self.cursor.execute(f"SELECT DISTINCT {qv[0]} FROM {qv[1]};")
            results = self.cursor.fetchall()
            for (i, result) in enumerate(results):
                print(f"{qv[2]} {i+1}: {result[0]}")

    def getDefaultScript(self):
        with open(Path(Path(__file__).parent.resolve(), self.script), "r") as f:
            queryText = "".join(f.readlines())
        return queryText

    def dayBells(self, date, room):
        """
        daybells: interrogate database for the musical signals on a date
        """
        queryText = self.getDefaultScript()
        queryText = queryText.replace("REPDATE", date).replace("ROOMNO", room)
        self.cursor.execute(queryText)
        rows = self.cursor.fetchall()
        # -- TODO WARNING rows = [{ ... }] is highly dependent on smerge.txt --- #
        rows = [
            {
                "date": row[0],
                "classTime": row[1],
                "classDismissTime": row[2],
                "offset": row[3],
                "end": bool(row[4]),
                "signal": row[5],
                "file": Path(self.music_dir, row[6]),
                "period": row[7],
                "cName": row[8],
                "section": row[9],
                "lesson": row[10],
            }
            for row in rows
        ]
        return rows

    def bellTime(self, bell):
        """calculate bell timing from signal data"""
        bellTime = bell["classDismissTime"] if bell["end"] else bell["classTime"]
        bellOffset = timedelta(minutes=(-1 if bell["end"] else 1) * bell["offset"])
        print(f"BELL DEBUG {bell['date']}, {bellTime}, {bellOffset} ===")
        try:
            bellDate = (
                dt.strptime(bell["date"] + " " + bellTime, "%m/%d/%Y %H:%M")
                + bellOffset
            )
        except TypeError:
            return None
        return bellDate


class CronScheduler:
    """Interface to cron
    Initialize with yaml file that specified runtime and cronuser
    """

    def __init__(self, yamlfile: str):
        y = yaml.safe_load_all(
            Path(Path(__file__).parent.resolve(), yamlfile).read_text()
        ).__next__()
        self.AMRUNTIME = (y["runtime"]["hour"], y["runtime"]["minute"])
        self.CRONUSER = y["user"]

    def scheduleBell(self, bell, testonly=False):
        """add a line to the cron file"""
        command = f"cvlc --play-and-exit {bell['file']}"
        if not bell["datetime"]:
            return
        print(f"BELL SCHEDULE: {bell['datetime']} {command}")
        # cvlc --random --play-and-exit /path/to/your/playlist
        with CronTab(user=self.CRONUSER) as cron:
            job = cron.new(command=command)
            job.setall(bell["datetime"])
            if not testonly:
                cron.write()

    def emptyCron(self):
        """clear out yesterday's cron events, keep the cron file short-ish"""
        with CronTab(user=self.CRONUSER) as cron:
            vlcJobs = cron.find_command("vlc")
            for job in vlcJobs:
                cron.remove(job)
            cron.write()

    def playDate(self, date: str, dB: SchedDB, testonly=False):
        """generate all the bells for a day"""
        self.emptyCron()
        for bell in dB.dayBells(date):
            bell["datetime"] = dB.bellTime(bell)
            if bell["datetime"]:
                self.scheduleBell(bell, testonly=testonly)

    def showCron(self):
        """it's easier to use the command line crontab -l"""
        with CronTab(user=self.CRONUSER) as cron:
            for job in cron:
                print(job)

    def initialize(self, room: str):
        """insert command into cronfile that will automatically generate the days bells"""
        with CronTab(user=self.CRONUSER) as cron:
            root_path = Path(__file__).parent.resolve()
            PYTHON = Path(root_path, "venv/bin/python")
            command = f"{PYTHON} {Path(root_path, Path(__file__))} -r {room}"
            job = cron.new(command=command)
            job.setall(f"{self.AMRUNTIME[1]} {self.AMRUNTIME[0]} * * *")
            cron.write()


def getargs(args=None):
    parser = argparse.ArgumentParser(description="CRON music scheduler for school")
    parser.add_argument(
        "-b", "--bellschedule", help="override schedule on calendar", default=None
    )
    parser.add_argument(
        "-c",
        "--cronList",
        help="show list of existing cron jobs",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "-i",
        "--initialize",
        help="install program in CRON for daily updates arg=room number",
        default=False,
    )
    parser.add_argument(
        "-l",
        "--list",
        help="show location of data and list available schedules and teachers",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "-o",
        "--overide",
        help='use a date other than today format "m/d/Y"',
        default=None,
    )
    parser.add_argument("-r", "--room", help="room number", default=None)
    parser.add_argument(
        "-t",
        "--test",
        help="run and print new bells, but do not schedule",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "-y", "--yamlfile", help=f"specify controlling YAML file ({YAML})", default=YAML
    )
    args = parser.parse_args(args=args)
    return args


def run(args=getargs(), testonly=False):
    sched_db = sqlite3.connect(":memory:")  # initialize dB
    sched_db_cursor = sched_db.cursor()
    sched_builder = SchedDB(
        args.yamlfile, sched_db_cursor
    )  # generate dB from .csv files
    scheduler = CronScheduler(args.yamlfile)  # cron interface

    if args.initialize:
        scheduler.initialize(room=args.initialize)
        return
    print(f"ARGS: {args}")
    if args.list:
        sched_builder.list()
        return
    if args.overide:
        today = args.overide
    else:
        today = dt.strftime(dt.today(), "%-m/%-d/%Y")
    if not args.room:
        raise argparse.ArgumentError(message="room number required to build schedule")
    bells = sched_builder.dayBells(today, room=args.room)
    if args.bellschedule:

        def newsignal(sd: dict, sig: str):
            sd["signal"] = sig
            return sd

        bells = [newsignal(bell, args.bellschedule) for bell in bells]
    if bells:
        scheduler.emptyCron()
        for bell in bells:
            bell["datetime"] = sched_builder.bellTime(bell)
            scheduler.scheduleBell(bell, testonly=args.test)
    if args.cronList:
        scheduler.showCron()


if __name__ == "__main__":
    run()
