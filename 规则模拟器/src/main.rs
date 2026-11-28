use endfield_sim::{Res, oracle::OracleRunner};
use std::{
    env, fs,
    io::{self, Write},
    path::Path,
    process::ExitCode,
};
fn run(path: &Path) -> Res<()> {
    let input = fs::read_to_string(path).map_err(|e| e.to_string())?;
    let mut out = io::BufWriter::new(io::stdout().lock());
    let result = OracleRunner::run(&input, &mut out);
    out.flush().map_err(|e| e.to_string())?;
    result
}
fn main() -> ExitCode {
    let paths: Vec<_> = env::args_os().skip(1).collect();
    let [path] = paths.as_slice() else {
        eprintln!("用法 endfield-sim <脚本.json>");
        return ExitCode::from(2);
    };
    match run(Path::new(path)) {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("{e}");
            ExitCode::FAILURE
        }
    }
}
