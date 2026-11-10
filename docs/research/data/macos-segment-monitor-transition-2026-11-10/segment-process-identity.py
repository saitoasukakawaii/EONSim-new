"""Identify a live segment without treating reaped/changed segments as solvers."""
def identify(live,current,stdout,executable):
 if live!=current or not stdout.strip():return None
 parts=stdout.strip().split(None,2)
 if len(parts)!=3:raise RuntimeError('Malformed ps identity: '+repr(stdout))
 pgid,state,cmd=parts
 if 'Z' in state:return None
 if int(pgid)!=live['pid'] or not cmd.startswith(executable+' -case case.json ') or f'-stop_after {live["target"]} ' not in cmd or 'T' in state:
  raise RuntimeError('Unexpected segment identity: '+repr(dict(live=live,ps=stdout)))
 return cmd
