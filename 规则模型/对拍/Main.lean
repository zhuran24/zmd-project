import «对拍».«执行»

def main (args : List String) : IO UInt32 := do
  let [file] := args | IO.eprintln "用法：lake exe 对拍 <脚本.json>"; return 2
  try
    Oracle.run file
    return 0
  catch err =>
    IO.eprintln err.toString
    return 1
