import sqlite3
path = r"d:\WpSystem\S-1-5-21-4217227049-1155704670-4225484024-500\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\Network\Cookies"
conn = sqlite3.connect(path)
rows = conn.execute("SELECT host_key, name, value FROM cookies WHERE host_key LIKE '%claude%'").fetchall()
if rows:
    for row in rows:
        print(row[0], "|", row[1], "|", row[2][:60])
else:
    print("暂无 claude.ai 相关 Cookie")
conn.close()
