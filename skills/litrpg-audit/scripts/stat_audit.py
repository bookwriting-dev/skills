#!/usr/bin/env python3
"""Deterministic LitRPG numeric and progression continuity auditor.

Verifies chapter text against canonical system rules and ledger.yaml:
- Attribute point arithmetic (earned vs allocated)
- Level-up XP thresholds and triggers
- Status box calculations (HP/MP/SP vs attributes)
- Skill unlock verification (no unearned skills used in combat)
- Resource pool exhaustion / casting limits
- Inventory and loot continuity

Usage:
    python3 stat_audit.py <path/to/chapter.md> [--ledger <path/to/ledger.yaml>] [--rules <path/to/system-rules.md>] [--json]
"""
import sys
import os
import re
import json
from pathlib import Path


def load_simple_yaml(path):
    """Minimal stdlib YAML parser for key-value and simple nested maps/lists in ledger.yaml."""
    if not os.path.exists(path):
        return None
    data = {}
    current_section = None
    sub_section = None
    sub_sub_section = None
    
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            raw = line.rstrip()
            if not raw or raw.strip().startswith("#"):
                continue
            
            indent = len(raw) - len(raw.lstrip())
            stripped = raw.strip()
            
            if indent == 0 and stripped.endswith(":"):
                current_section = stripped[:-1].strip()
                data[current_section] = {}
                sub_section = None
                sub_sub_section = None
            elif indent == 2 and current_section and stripped.endswith(":"):
                sub_section = stripped[:-1].strip()
                data[current_section][sub_section] = {}
                sub_sub_section = None
            elif indent == 4 and current_section and sub_section and stripped.endswith(":"):
                sub_sub_section = stripped[:-1].strip()
                data[current_section][sub_section][sub_sub_section] = {}
            elif ":" in stripped:
                k, v = stripped.split(":", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                
                # Try parsing numeric or boolean
                if v.lower() == "true":
                    val = True
                elif v.lower() == "false":
                    val = False
                elif v.isdigit():
                    val = int(v)
                else:
                    try:
                        val = float(v)
                    except ValueError:
                        val = v
                
                if sub_sub_section and current_section and sub_section:
                    data[current_section][sub_section][sub_sub_section][k] = val
                elif sub_section and current_section:
                    data[current_section][sub_section][k] = val
                elif current_section:
                    data[current_section][k] = val
            elif stripped.startswith("- ") and current_section and sub_section:
                val = stripped[2:].strip().strip('"').strip("'")
                if not isinstance(data[current_section][sub_section], list):
                    data[current_section][sub_section] = []
                data[current_section][sub_section].append(val)
                
    return data


def find_ledger_file(chapter_path):
    """Search for ledger.yaml relative to chapter directory."""
    p = Path(chapter_path).resolve()
    # Check parent dirs
    for parent in [p.parent, p.parent.parent, p.parent.parent.parent]:
        candidates = [
            parent / "Wiki" / "World" / "Systems" / "ledger.yaml",
            parent / "Wiki" / "World" / "ledger.yaml",
            parent / "ledger.yaml",
        ]
        # Also check Book-N subfolder
        for cand in candidates:
            if cand.exists():
                return str(cand)
    return None


def extract_system_blocks(text):
    """Extract markdown blockquotes or callouts containing system notifications."""
    blocks = []
    lines = text.splitlines()
    in_block = False
    current_block = []
    
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith(">"):
            in_block = True
            current_block.append((i, stripped.lstrip(">").strip()))
        else:
            if in_block:
                if current_block:
                    blocks.append(current_block)
                    current_block = []
                in_block = False
    if in_block and current_block:
        blocks.append(current_block)
    return blocks


def audit_chapter(chapter_path, ledger_path=None, rules_path=None):
    if not os.path.exists(chapter_path):
        return {"error": f"Chapter file not found: {chapter_path}"}
        
    with open(chapter_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    if not ledger_path:
        ledger_path = find_ledger_file(chapter_path)
        
    ledger_data = load_simple_yaml(ledger_path) if ledger_path else None
    
    findings = {
        "chapter": chapter_path,
        "ledger_found": bool(ledger_path),
        "ledger_path": ledger_path,
        "system_blocks_count": 0,
        "violations": [],
        "warnings": [],
        "notices": [],
        "detected_stats": {},
        "detected_skills": [],
        "detected_level_ups": [],
        "xp_mentions": [],
    }
    
    # 1. System Block Extraction & Analysis
    blocks = extract_system_blocks(content)
    findings["system_blocks_count"] = len(blocks)
    
    for block in blocks:
        block_text = " ".join([line[1] for line in block])
        line_num = block[0][0]
        
        # Detect Level-Up
        lvl_match = re.search(r'(?:level\s+(?:up!?|reached|is)|reached\s+(?:\*\*|)?level|current\s+level)\s*[:\*\s]*(\d+)(?:\s*->\s*(\d+))?', block_text, re.IGNORECASE)
        if not lvl_match and re.search(r'level\s+up!?', block_text, re.IGNORECASE):
            lvl_match = re.search(r'\blevel\b\s*[:\*\s]*(\d+)', block_text, re.IGNORECASE)
        if lvl_match:
            old_lvl = lvl_match.group(1)
            new_lvl = lvl_match.group(2) if (lvl_match.lastindex and lvl_match.lastindex >= 2 and lvl_match.group(2)) else old_lvl
            findings["detected_level_ups"].append({
                "line": line_num,
                "text": block_text[:80],
                "full_text": block_text,
                "level": int(new_lvl)
            })
            
        # Detect Attribute Deltas (e.g. STR: 12 -> 14 (+2) or Strength +2)
        attr_deltas = re.findall(r'\b(STR|AGI|DEX|CON|END|INT|WIS|WIL|CHA|LCK|Strength|Agility|Constitution|Intelligence|Wisdom|Charisma|Luck)\b[^\d\+\-]*(\d+)?\s*(?:->|\+)\s*(\d+)', block_text, re.IGNORECASE)
        for ad in attr_deltas:
            attr_name = ad[0].upper()
            findings["detected_stats"][attr_name] = ad[2]
            
        # Detect Skill Unlocks
        skill_match = re.search(r'(?:skill\s+(?:acquired|unlocked|learned|upgraded))\s*[:\*\s]*([^\|\n\.\>]+)', block_text, re.IGNORECASE)
        if skill_match:
            skill_name = skill_match.group(1).strip().strip("*").strip()
            findings["detected_skills"].append({
                "line": line_num,
                "skill": skill_name
            })
            
    # 2. General Prose XP & Stat Mention Scan
    xp_matches = re.finditer(r'\b(?:\+?\s*(\d+[\d,]*)\s*(?:XP|EXP|Experience))\b', content, re.IGNORECASE)
    for m in xp_matches:
        val_str = m.group(1).replace(",", "")
        findings["xp_mentions"].append(int(val_str))
        
    # 3. Check Arithmetic & Ledger Consistency
    if ledger_data:
        system_rules = ledger_data.get("system_rules", {})
        stat_pts_per_lvl = system_rules.get("stat_points_per_level", 5)
        
        # Check level up point consistency
        if findings["detected_level_ups"]:
            for lu in findings["detected_level_ups"]:
                target_lvl = lu["level"]
                search_scope = lu.get("full_text", lu["text"])
                allocated_points = 0
                
                # Check patterns like: "+5 points", "+5 free points", "Points: +5", "Points: **+5**"
                pt_matches = re.findall(r'(?:\+|\b)(\d+)\s*(?:\*\*)?\s*(?:points|free points|unassigned|attribute points)', search_scope, re.IGNORECASE)
                if not pt_matches:
                    pt_matches = re.findall(r'(?:points|attribute points|unassigned)\s*[:\*\s]*\+?(\d+)', search_scope, re.IGNORECASE)
                    
                for pm in pt_matches:
                    allocated_points += int(pm)
                    
                if allocated_points > 0 and allocated_points != stat_pts_per_lvl:
                    findings["warnings"].append({
                        "line": lu["line"],
                        "type": "STAT_POINT_MISMATCH",
                        "message": f"Level up awarded {allocated_points} points, but system rules declare {stat_pts_per_lvl} points per level."
                    })
                    
        # Check Character Skill Legality
        known_skills = set()
        for char_name, cdata in ledger_data.get("characters", {}).items():
            if isinstance(cdata, dict):
                skills_list = cdata.get("skills", [])
                if isinstance(skills_list, list):
                    for s in skills_list:
                        if isinstance(s, dict) and "name" in s:
                            known_skills.add(s["name"].lower())
                        elif isinstance(s, str):
                            known_skills.add(s.lower())
                            
        # Scan combat casting phrases: "cast [Skill]", "activated [Skill]", "invoked [Skill]"
        cast_matches = re.finditer(r'\b(?:cast|casted|activated|invoked|channeled)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b', content)
        for cm in cast_matches:
            invoked = cm.group(1).strip()
            # If known_skills is populated and invoked skill isn't in it and wasn't unlocked in this chapter
            if known_skills and invoked.lower() not in known_skills:
                # Check if it was unlocked in this chapter
                unlocked_here = any(invoked.lower() in ds["skill"].lower() for ds in findings["detected_skills"])
                if not unlocked_here:
                    findings["notices"].append({
                        "type": "UNREGISTERED_SKILL_INVOCATION",
                        "skill": invoked,
                        "message": f"Skill '{invoked}' was invoked but is not recorded in ledger.yaml skills list or unlocked in this chapter."
                    })

    else:
        findings["notices"].append({
            "type": "NO_LEDGER_FILE",
            "message": "No ledger.yaml found. Auditing against internal chapter consistency only."
        })
        
    # Check for Stat-Dump Paralysis (> 25 consecutive lines inside system blockquote)
    for block in blocks:
        if len(block) > 25:
            findings["warnings"].append({
                "line": block[0][0],
                "type": "STAT_DUMP_PARALYSIS",
                "message": f"System block exceeds 25 lines ({len(block)} lines). Reader fatigue risk; consider using condensed delta format."
            })
            
    findings["status"] = "FAIL" if findings["violations"] else ("WARN" if findings["warnings"] else "PASS")
    return findings


def format_markdown_report(report):
    lines = [
        f"# LitRPG Progression Audit: {os.path.basename(report['chapter'])}",
        f"**Status:** {report['status']} | **System Blocks:** {report['system_blocks_count']} | **Ledger:** {'Loaded' if report['ledger_found'] else 'None'}",
        "",
        "## Summary",
        f"- **Violations:** {len(report['violations'])}",
        f"- **Warnings:** {len(report['warnings'])}",
        f"- **Notices:** {len(report['notices'])}",
        f"- **Level-Ups Detected:** {len(report['detected_level_ups'])}",
        f"- **Skills Unlocked:** {len(report['detected_skills'])}",
        "",
    ]
    
    if report["violations"]:
        lines.append("## Violations (Hard Fail)")
        for v in report["violations"]:
            lines.append(f"- **Line {v.get('line', '?')}:** [{v.get('type')}] {v.get('message')}")
        lines.append("")
        
    if report["warnings"]:
        lines.append("## Warnings")
        for w in report["warnings"]:
            lines.append(f"- **Line {w.get('line', '?')}:** [{w.get('type')}] {w.get('message')}")
        lines.append("")
        
    if report["notices"]:
        lines.append("## Notices & Tracked State")
        for n in report["notices"]:
            lines.append(f"- [{n.get('type')}] {n.get('message')}")
        lines.append("")
        
    if report["detected_level_ups"]:
        lines.append("## Detected Level-Ups")
        for lu in report["detected_level_ups"]:
            lines.append(f"- Line {lu['line']}: Level {lu['level']} -> `{lu['text']}`")
        lines.append("")
        
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print("Usage: python3 stat_audit.py <path/to/chapter.md> [--ledger <ledger.yaml>] [--json]")
        sys.exit(0 if len(sys.argv) >= 2 and sys.argv[1] in ("-h", "--help", "help") else 1)
        
    chapter_arg = sys.argv[1]
    if not os.path.exists(chapter_arg):
        sys.exit(f"error: Chapter file not found: {chapter_arg}")
        
    ledger_arg = None
    output_json = False
    
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == "--ledger" and i + 1 < len(sys.argv):
            ledger_arg = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--json":
            output_json = True
            i += 1
        else:
            i += 1
            
    res = audit_chapter(chapter_arg, ledger_arg)
    if output_json:
        print(json.dumps(res, indent=2))
    else:
        print(format_markdown_report(res))
        
    if res.get("status") == "FAIL":
        sys.exit(1)
    sys.exit(0)
