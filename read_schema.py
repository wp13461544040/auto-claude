import sqlite3
path = r"d:\WpSystem\S-1-5-21-4217227049-1155704670-4225484024-500\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\Network\Cookies"
conn = sqlite3.connect(path)
# 表结构
print("=== cookies 表结构 ===")
for row in conn.execute("PRAGMA table_info(cookies)").fetchall():
    print(row)
# 取一行样本
print("\n=== 样本行（完整字段）===")
row = conn.execute("SELECT * FROM cookies LIMIT 1").fetchone()
if row:
    cols = [d[0] for d in conn.execute("PRAGMA table_info(cookies)").fetchall()]
    for k, v in zip(cols, row):
        print(f"  {k}: {repr(v)[:80]}")
conn.close()
