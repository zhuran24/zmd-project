import «对拍».«场地»

open Lean Std.Internal.Parsec Std.Internal.Parsec.String

-- 两种顶层都只有两个字段。版本在前时跳过它的词形，完整语法由各模式的解析器检查。
private def gridHeader : Parser Bool := do
  ws
  skipString "{"
  ws
  skipString "\""
  match ← Json.Parser.str with
  | "场地" => return true
  | "版本" =>
    ws
    skipString ":"
    ws
    repeat
      let c ← peek!
      if c == ',' then break
      if !("-+0123456789.eE \t\r\n".contains c) then return false
      skip
    skip
    ws
    skipString "\""
    return (← Json.Parser.str) == "场地"
  | _ => return false

def main (args : List String) : IO UInt32 := do
  let [file] := args | IO.eprintln "用法：lake exe 对拍 <脚本.json>"; return 2
  try
    let source ← IO.FS.readFile file
    let grid := (Parser.run gridHeader source).toOption == some true
    let entries ← Oracle.ioResult file do
      if grid then Oracle.Grid.plainNumbers source
      let j ← Oracle.StrictJson.parse source
      let k := if grid then "场地" else "段"
      Oracle.checkKeys j ["版本", k]
      unless (← (← Oracle.key j "版本").getNat?) == 1 do throw "只支持版本 1"
      (← Oracle.key j k).getArr?
    let out ← IO.getStdout
    let emit := fun (row : Json) => out.putStrLn row.compress
    for (j,i) in entries.toList.zipIdx do
      if grid then Oracle.Grid.runExample j (i+1) emit
      else Oracle.runSegment j (i+1) emit
    return 0
  catch err =>
    IO.eprintln err.toString
    return 1
