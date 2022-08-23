SELECT c.Date, b.startTime, b.endTime, l.dt, l.end, l.signal, m.music, t.periodBegin,  t.class, t.section, l.lessontype
    FROM calendar as c 
    CROSS JOIN teachers as t
        ON c.DAY = t.weekDay
    LEFT JOIN bells as b 
        ON c.schedule = b.schedule AND t.periodBegin = b.period
    CROSS JOIN classes as l 
        ON l.cname = t.class
    LEFT JOIN music as m 
        ON l.signal = m.signal AND l.cname = m.cname
    WHERE c.DATE = "REPDATE" AND t.room = "ROOMNO";