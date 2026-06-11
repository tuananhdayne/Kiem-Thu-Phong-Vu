import json
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = PROJECT_ROOT / "reports" / "one_by_one_verify"
SUMMARY_JSON = REPORT_DIR / "summary.json"
SUMMARY_MD = REPORT_DIR / "summary.md"
EXPECTED_FAIL_NAMES = {"test_search_very_long_query"}


def _run(cmd, env=None, timeout=None):
    return subprocess.run(
        cmd,
        cwd=str(PROJECT_ROOT),
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
    )


def collect_nodeids(env):
    cmd = [
        sys.executable,
        "-B",
        "-m",
        "pytest",
        "--collect-only",
        "-q",
        "-o",
        "addopts=",
        "tests",
        "--run-security",
        "--run-destructive",
    ]
    proc = _run(cmd, env=env, timeout=120)
    nodeids = []
    for line in proc.stdout.splitlines():
        text = line.strip()
        if text.startswith("tests") and "::" in text:
            nodeids.append(text)
    if not nodeids:
        print(proc.stdout)
        raise SystemExit("No tests collected.")
    return nodeids


def parse_junit(path):
    if not path.exists():
        return {"status": "NO_XML", "time": 0.0, "message": "JUnit file was not created."}
    root = ET.parse(path).getroot()
    testcase = next(root.iter("testcase"), None)
    if testcase is None:
        return {"status": "NO_CASE", "time": 0.0, "message": "No testcase in JUnit XML."}
    status = "PASS"
    message = ""
    for child in list(testcase):
        tag = child.tag.split("}")[-1]
        if tag == "failure":
            status = "FAIL"
            message = child.attrib.get("message") or (child.text or "")
            break
        if tag == "error":
            status = "ERROR"
            message = child.attrib.get("message") or (child.text or "")
            break
        if tag == "skipped":
            status = "SKIP"
            message = child.attrib.get("message") or ""
            break
    return {
        "status": status,
        "time": float(testcase.attrib.get("time", "0") or 0),
        "message": " ".join(message.split())[:500],
    }


def safe_name(nodeid):
    cleaned = []
    for char in nodeid:
        cleaned.append(char if char.isalnum() else "_")
    return "".join(cleaned).strip("_")[:150]


def append_markdown(rows):
    lines = [
        "# One-by-one verification",
        "",
        "| # | Status | Time (s) | Test | Log | Note |",
        "|---:|---|---:|---|---|---|",
    ]
    for idx, row in enumerate(rows, 1):
        note = row.get("message", "").replace("|", "\\|")
        lines.append(
            f"| {idx} | {row['status']} | {row['time']:.2f} | `{row['nodeid']}` | `{Path(row['log']).name}` | {note} |"
        )
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(
        {
            "RUN_ID": "one_by_one_verify_20260611",
            "SELENIUM_ISOLATE_EACH_TEST": "1",
            "SELENIUM_HEADLESS": "1",
            "SELENIUM_BLOCK_IMAGES": "1",
            "SELENIUM_COMMAND_TIMEOUT": "30",
            "SELENIUM_SAVE_PASS": "0",
            "SELENIUM_CAPTURE_DESTRUCTIVE_ARTIFACTS": "1",
            "SELENIUM_CAPTURE_DESTRUCTIVE_SCREENSHOT": "1",
            "VERY_LONG_SAVE_PROGRESS": "1",
            "VERY_LONG_SAVE_PROGRESS_EVERY": "2",
            "VERY_LONG_COMMAND_TIMEOUT": "8",
            "VERY_LONG_QUERY_CHUNK_SIZE": "2000000",
            "VERY_LONG_QUERY_ITERATIONS": "20",
        }
    )

    nodeids = collect_nodeids(env)
    rows = []
    print(f"Collected {len(nodeids)} tests.")

    for index, nodeid in enumerate(nodeids, 1):
        name = safe_name(nodeid)
        junit_path = REPORT_DIR / f"{index:02d}_{name}.xml"
        html_path = REPORT_DIR / f"{index:02d}_{name}.html"
        cmd = [
            sys.executable,
            "-B",
            "-m",
            "pytest",
            "-q",
            "-o",
            "addopts=",
            nodeid,
            "--run-security",
            "--run-destructive",
            f"--html={html_path}",
            "--self-contained-html",
            f"--junitxml={junit_path}",
        ]
        started = time.perf_counter()
        proc = _run(cmd, env=env, timeout=420)
        parsed = parse_junit(junit_path)
        duration = time.perf_counter() - started
        stdout_path = REPORT_DIR / f"{index:02d}_{name}.log"
        stdout_path.write_text(proc.stdout, encoding="utf-8")
        test_name = nodeid.split("::")[-1].split("[", 1)[0]
        expected_fail = test_name in EXPECTED_FAIL_NAMES
        row = {
            "index": index,
            "nodeid": nodeid,
            "status": parsed["status"],
            "time": parsed["time"] or duration,
            "returncode": proc.returncode,
            "expected_fail": expected_fail,
            "message": parsed["message"],
            "junit": str(junit_path),
            "html": str(html_path),
            "log": str(stdout_path),
            "checked_at": datetime.now().isoformat(timespec="seconds"),
        }
        rows.append(row)
        SUMMARY_JSON.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        append_markdown(rows)

        label = "EXPECTED_FAIL" if expected_fail and parsed["status"] in {"FAIL", "ERROR"} else parsed["status"]
        print(f"[{index:02d}/{len(nodeids):02d}] {label:13} {row['time']:7.2f}s {nodeid}")
        if parsed["message"]:
            print(f"    {parsed['message']}")

        if parsed["status"] in {"FAIL", "ERROR"} and not expected_fail:
            print(f"Unexpected failure. Wrote log: {stdout_path}")
            raise SystemExit(2)

    unexpected = [
        row for row in rows
        if row["status"] in {"FAIL", "ERROR"} and not row["expected_fail"]
    ]
    print(f"Done. Unexpected failures: {len(unexpected)}. Summary: {SUMMARY_MD}")
    raise SystemExit(0 if not unexpected else 2)


if __name__ == "__main__":
    main()
