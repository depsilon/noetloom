Interpreter: 3.13.13 (main, Apr  7 2026, 18:19:01) [Clang 21.0.0 (clang-2100.0.123.102)]
README command smoke check; only file destinations and TOKEN are substituted.
README: python3.13 -B -m toolshelf --db library.sqlite3 add D-001 "Cordless drill"
$ /opt/homebrew/opt/python@3.13/bin/python3.13 -B -m toolshelf --db /private/tmp/noetloom-autonomous-tool-shelf-3lgpp0_3/evidence/readme-09529dux/library.sqlite3 add D-001 'Cordless drill'
exit=0
Added d-001.


README: python3.13 -B -m toolshelf --db library.sqlite3 add H-001 "Claw hammer"
$ /opt/homebrew/opt/python@3.13/bin/python3.13 -B -m toolshelf --db /private/tmp/noetloom-autonomous-tool-shelf-3lgpp0_3/evidence/readme-09529dux/library.sqlite3 add H-001 'Claw hammer'
exit=0
Added h-001.


README: python3.13 -B -m toolshelf --db library.sqlite3 inventory
$ /opt/homebrew/opt/python@3.13/bin/python3.13 -B -m toolshelf --db /private/tmp/noetloom-autonomous-tool-shelf-3lgpp0_3/evidence/readme-09529dux/library.sqlite3 inventory
exit=0
asset_id	name	status	borrower	due_on
d-001	Cordless drill	available		
h-001	Claw hammer	available		


README: python3.13 -B -m toolshelf --db library.sqlite3 lend " d-001 " "Alex María" --due 2026-10-06 --on 2026-10-01
$ /opt/homebrew/opt/python@3.13/bin/python3.13 -B -m toolshelf --db /private/tmp/noetloom-autonomous-tool-shelf-3lgpp0_3/evidence/readme-09529dux/library.sqlite3 lend ' d-001 ' 'Alex María' --due 2026-10-06 --on 2026-10-01
exit=0
Loan 1: lent d-001.


README: python3.13 -B -m toolshelf --db library.sqlite3 inventory --available
$ /opt/homebrew/opt/python@3.13/bin/python3.13 -B -m toolshelf --db /private/tmp/noetloom-autonomous-tool-shelf-3lgpp0_3/evidence/readme-09529dux/library.sqlite3 inventory --available
exit=0
asset_id	name	status	borrower	due_on
h-001	Claw hammer	available		


README: python3.13 -B -m toolshelf --db library.sqlite3 overdue --as-of 2026-10-06
$ /opt/homebrew/opt/python@3.13/bin/python3.13 -B -m toolshelf --db /private/tmp/noetloom-autonomous-tool-shelf-3lgpp0_3/evidence/readme-09529dux/library.sqlite3 overdue --as-of 2026-10-06
exit=0
loan_id	asset_id	name	borrower	lent_on	due_on	returned_on


README: python3.13 -B -m toolshelf --db library.sqlite3 overdue --as-of 2026-10-07
$ /opt/homebrew/opt/python@3.13/bin/python3.13 -B -m toolshelf --db /private/tmp/noetloom-autonomous-tool-shelf-3lgpp0_3/evidence/readme-09529dux/library.sqlite3 overdue --as-of 2026-10-07
exit=0
loan_id	asset_id	name	borrower	lent_on	due_on	returned_on
1	d-001	Cordless drill	Alex María	2026-10-01	2026-10-06	


README: python3.13 -B -m toolshelf --db library.sqlite3 return D-001 --on 2026-10-07
$ /opt/homebrew/opt/python@3.13/bin/python3.13 -B -m toolshelf --db /private/tmp/noetloom-autonomous-tool-shelf-3lgpp0_3/evidence/readme-09529dux/library.sqlite3 return D-001 --on 2026-10-07
exit=0
Loan 1: returned d-001.


README: python3.13 -B -m toolshelf --db library.sqlite3 lend D-001 Sam --due 2026-10-10 --on 2026-10-08
$ /opt/homebrew/opt/python@3.13/bin/python3.13 -B -m toolshelf --db /private/tmp/noetloom-autonomous-tool-shelf-3lgpp0_3/evidence/readme-09529dux/library.sqlite3 lend D-001 Sam --due 2026-10-10 --on 2026-10-08
exit=0
Loan 2: lent d-001.


README: python3.13 -B -m toolshelf --db library.sqlite3 loans
$ /opt/homebrew/opt/python@3.13/bin/python3.13 -B -m toolshelf --db /private/tmp/noetloom-autonomous-tool-shelf-3lgpp0_3/evidence/readme-09529dux/library.sqlite3 loans
exit=0
loan_id	asset_id	name	borrower	lent_on	due_on	returned_on
1	d-001	Cordless drill	Alex María	2026-10-01	2026-10-06	2026-10-07
2	d-001	Cordless drill	Sam	2026-10-08	2026-10-10	


README: python3.13 -B -m toolshelf --db library.sqlite3 loans --active
$ /opt/homebrew/opt/python@3.13/bin/python3.13 -B -m toolshelf --db /private/tmp/noetloom-autonomous-tool-shelf-3lgpp0_3/evidence/readme-09529dux/library.sqlite3 loans --active
exit=0
loan_id	asset_id	name	borrower	lent_on	due_on	returned_on
2	d-001	Cordless drill	Sam	2026-10-08	2026-10-10	


README: python3.13 -B -m toolshelf --db library.sqlite3 import new-tools.csv
$ /opt/homebrew/opt/python@3.13/bin/python3.13 -B -m toolshelf --db /private/tmp/noetloom-autonomous-tool-shelf-3lgpp0_3/evidence/readme-09529dux/library.sqlite3 import /private/tmp/noetloom-autonomous-tool-shelf-3lgpp0_3/evidence/readme-09529dux/new-tools.csv
exit=0
line	asset_id	name
2	s-001	Scie, précision
3	strasse-2	"Équerre ""atelier"""
Preview: 2 tools; no data written.
Preview token: 66abfebd302f2de7a462f087600047e830f6ab06f9483ca9e2c5c798adcbb77a
To apply this unchanged file and catalog, repeat import with --confirm TOKEN.


README: python3.13 -B -m toolshelf --db library.sqlite3 import new-tools.csv --confirm TOKEN
$ /opt/homebrew/opt/python@3.13/bin/python3.13 -B -m toolshelf --db /private/tmp/noetloom-autonomous-tool-shelf-3lgpp0_3/evidence/readme-09529dux/library.sqlite3 import /private/tmp/noetloom-autonomous-tool-shelf-3lgpp0_3/evidence/readme-09529dux/new-tools.csv --confirm 66abfebd302f2de7a462f087600047e830f6ab06f9483ca9e2c5c798adcbb77a
exit=0
Imported 2 tools.


README: python3.13 -B -m toolshelf --db library.sqlite3 export library-backup.zip
$ /opt/homebrew/opt/python@3.13/bin/python3.13 -B -m toolshelf --db /private/tmp/noetloom-autonomous-tool-shelf-3lgpp0_3/evidence/readme-09529dux/library.sqlite3 export /private/tmp/noetloom-autonomous-tool-shelf-3lgpp0_3/evidence/readme-09529dux/library-backup.zip
exit=0
Exported to /private/tmp/noetloom-autonomous-tool-shelf-3lgpp0_3/evidence/readme-09529dux/library-backup.zip.


Extracted library.sqlite3 into a new restored.sqlite3 as instructed.
README: python3.13 -B -m toolshelf --db restored.sqlite3 inventory
$ /opt/homebrew/opt/python@3.13/bin/python3.13 -B -m toolshelf --db /private/tmp/noetloom-autonomous-tool-shelf-3lgpp0_3/evidence/readme-09529dux/restored.sqlite3 inventory
exit=0
asset_id	name	status	borrower	due_on
d-001	Cordless drill	loaned	Sam	2026-10-10
h-001	Claw hammer	available		
s-001	Scie, précision	available		
strasse-2	"Équerre ""atelier"""	available		


README: python3.13 -B -m toolshelf --db restored.sqlite3 loans
$ /opt/homebrew/opt/python@3.13/bin/python3.13 -B -m toolshelf --db /private/tmp/noetloom-autonomous-tool-shelf-3lgpp0_3/evidence/readme-09529dux/restored.sqlite3 loans
exit=0
loan_id	asset_id	name	borrower	lent_on	due_on	returned_on
1	d-001	Cordless drill	Alex María	2026-10-01	2026-10-06	2026-10-07
2	d-001	Cordless drill	Sam	2026-10-08	2026-10-10	


README: python3.13 -B -m toolshelf --help
$ /opt/homebrew/opt/python@3.13/bin/python3.13 -B -m toolshelf --help
exit=0
usage: toolshelf [-h] [--db DB]
                 {add,inventory,lend,return,loans,overdue,import,export} ...

ToolShelf — an offline neighborhood tool library.

positional arguments:
  {add,inventory,lend,return,loans,overdue,import,export}
    add                 Add a uniquely identified tool
    inventory           List tools and current availability
    lend                Lend an available tool
    return              Close the active loan for a tool
    loans               List all loan history
    overdue             List current loans overdue on an explicit date
    import              Preview CSV, or apply an unchanged confirmed preview
    export              Export catalog, inventory, loans and database to a new
                        ZIP

options:
  -h, --help            show this help message and exit
  --db DB               SQLite file (default: ./toolshelf.sqlite3)


README: python3.13 -B -m toolshelf import --help
$ /opt/homebrew/opt/python@3.13/bin/python3.13 -B -m toolshelf import --help
exit=0
usage: toolshelf import [-h] [--confirm TOKEN] csv_file

positional arguments:
  csv_file         UTF-8 CSV with asset_id,name headers

options:
  -h, --help       show this help message and exit
  --confirm TOKEN  Token printed by the unchanged preview


$ python3 -B -m toolshelf --help
exit=1

Error: ToolShelf requires Python 3.11+; try python3.13 on this machine.

PASS: 18 README CLI examples exited 0; restored outputs matched; older interpreter reported the supported version without a traceback.
