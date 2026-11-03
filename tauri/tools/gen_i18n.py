"""Gera tauri/src/i18n.ts a partir de src/i18n.py e src/help_dialog.py,
para os textos da interface terem uma fonte só. Rodar: python tauri/tools/gen_i18n.py"""
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def literal(file, name):
    tree = ast.parse((ROOT / "src" / file).read_text(encoding="utf-8"))
    node = next(n for n in tree.body
                if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", None) == name)
    return ast.literal_eval(node.value)


def dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2)


out = ROOT / "tauri" / "src" / "i18n.ts"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(
    "// GERADO por tools/gen_i18n.py. Não edite à mão: mude src/i18n.py ou src/help_dialog.py e rode de novo.\n"
    f"export const STRINGS: Record<string, Record<string, string>> = {dump(literal('i18n.py', 'STRINGS'))};\n\n"
    f"export const HELP: Record<string, [string, string][]> = {dump(literal('help_dialog.py', 'HELP_CONTENT'))};\n",
    encoding="utf-8",
)
print("ok:", out)
