p = "backend/tests/test_skills_zoo_readme_traversal_security.py"
lines = open(p, "rb").read().decode("utf-8", errors="replace").splitlines()
print("TOTAL LINES:", len(lines))
for i in range(min(16, len(lines))):
    print(i + 1, repr(lines[i]))
</｜DSML｜ parameter>