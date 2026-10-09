import re

with open('lite.html', 'r') as f:
    c = f.read()

c = c.replace("${state.reason.replace('[🔥BB]'", "${(state.reason || '').replace('[🔥BB]'")

with open('lite.html', 'w') as f:
    f.write(c)

