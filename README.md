# csv-music-scheduler
Raspberry Pi scheduler to set musical queues based on bell schedule and teacher schedule.

# Approach

A simple way to make a scheduling player on the Pi was suggested by [J. Bowman](https://gist.github.com/gitblight1) in a [gist](https://gist.github.com/gitblight1/602f0a73672822c1ef6b056ff35ea293): use [vlc](https://www.videolan.org/vlc/), which comes with a command line interface `cvlc` that is [documented here](https://wiki.videolan.org/Documentation:Streaming_HowTo/Command_Line_Examples/) and also maybe [here](https://openbase.com/js/cvlc/documentation).

The key command is:

```
cvlc --play-and-exit fname
```

To test successful scheduling, use `crontab -l` and to manually check the player, edit the cronfile with `crontab -e`.

For my purposes, this is a python program to schedule multiple short musical signals. It calculates the timing using on a set of .csv files that can be merged to build a schedule.

## Scheduling basics

There is a bell schedule which defines when classes begin and end.
The bell schedule may change on the fly and it may be pretty complicated.

There is also a teacher's schedule which determines which classes the teacher is actually teaching.

Then there is the musical schedule for each class, eg: t=0, play a hello tune, t=5min, play a now we begin tune, t=END-5min play a checkout tune.
And there needs to be a way to switch schedules when there is a delayed opening or some other event.

All these files can be managed by hand, all are `.csv`.
### bell schedule `bells.csv`

`schedule, period, startTime, endTime`

### teacher schedule `teachers.csv`

`teacher, weekDay, periodBegin, periodEnd, room, class, section`


### class schedule `class.csv`

`cname, lessontype, signal, dt, end(after-start=0/before-end=1)`

### music selection `music.csv`

`cname, lessontype, signal, music fname`

### calendar `calendar.csv`

`Date,Day,full,schedule,classDay,Week,MP,Note`

## usage

```
usage: csv-music.py [-h] [-i] [-o OVERIDE] [-b BELLSCHEDULE] [-l] [-t] [-c]

CRON music scheduler for school

optional arguments:
  -h, --help            show this help message and exit
  -i, --initialize      install program in CRON for daily updates
  -o OVERIDE, --overide OVERIDE
                        use a date other than today format "m/d/Y"
  -b BELLSCHEDULE, --bellschedule BELLSCHEDULE
                        override schedule on calendar
  -l, --list            show location of data and list available schedules and teachers
  -t, --test            run and print new bells, but do not schedule
  -c, --cronList        show list of existing cron jobs
  -y YAMLFILE, --yamlfile YAMLFILE
                        specify controlling YAML file (csv-music.yaml)

```

On Raspberry Pi runs as user `pi`.

On first downloading to your Pi, run 

`python csv-music.py -i` 

to insert a line into the Cronfile that will run the program every morning.


## implementation

1. Python 3.8
1. uses packages `crontab`, `csv`, and `sqlite3` (for all the joins to get specific times from the list of schedules).
1. add a real time clock to the Pi so that it can be scooped away, set, returned. And so that it can work without recourse to the internet.
1. find some decent music.

## BUGS

1. Sched_db.daybells : the conversion of query output to a dictionary for scheduling depends on the content of `merge.txt` so if it is edited, this conversion row must be updated in the code.




