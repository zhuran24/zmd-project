"""GDB Python script: observe existing functions without changing source or input files."""
import gdb, json
seen=set()
class Trace(gdb.Breakpoint):
    def stop(self):
        frame=gdb.newest_frame(); names=[]
        while frame is not None and len(names)<10:
            names.append(frame.name() or '?'); frame=frame.older()
        relevant=any('verify_record_at' in n or 'verify_cycle_at' in n for n in names)
        if relevant:
            key=tuple(names[:5])
            if key not in seen:
                seen.add(key)
                print('R5_CALLPATH '+json.dumps(names[:5],ensure_ascii=False))
        return False
for name in ['kernel::output::run_record','kernel::cycle::search','kernel::engine::Engine::new_production','kernel::engine::Engine::step_tick']:
    Trace(name,internal=True)
