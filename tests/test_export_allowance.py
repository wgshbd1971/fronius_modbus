"""Temporary meter-following allowances preserve normal export and restore safely."""
import ast,asyncio,copy,types,unittest
from pathlib import Path
from unittest.mock import AsyncMock,Mock,patch
ROOT=Path(__file__).resolve().parents[1]/'custom_components/fronius_modbus'
def functions(file,names,globals):
 tree=ast.parse((ROOT/file).read_text());nodes=[]
 for n in ast.walk(tree):
  if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in names:
   n.decorator_list=[];nodes.append(n)
 module=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),*nodes],type_ignores=[])
 exec(compile(ast.fix_missing_locations(module),str(ROOT/file),'exec'),globals)
 return globals
class Wire:
 def __init__(self,limit=0):self.limit=limit;self.writes=[]
 async def async_get_power_limits(self):return {'exportLimits':{'activePower':{'activated':True,'softLimit':{'enabled':True,'powerLimit':self.limit}}},'visualization':{'wattPeakReferenceValue':10000}}
 async def async_set_soft_export_limit(self,watts):self.writes.append(watts);self.limit=watts;return await self.async_get_power_limits()
def hub(limit=0,normal=10000):
 n=functions('hub.py',{'_refresh_rest_export_limit','set_export_limit'},{});h=types.SimpleNamespace(data={},_normal_export_limit_w=normal,_rest_client=Wire(limit),rest_export_control_configured=True,_notify_entities=Mock())
 for k in ['_refresh_rest_export_limit','set_export_limit']:setattr(h,k,types.MethodType(n[k],h))
 return h
class LimitTests(unittest.IsolatedAsyncioTestCase):
 async def test_temporary_positive_readback_does_not_replace_normal_limit(self):
  h=hub();self.assertTrue(await h.set_export_limit(100));await h._refresh_rest_export_limit()
  self.assertEqual(h.data['rest_export_limit_w'],100);self.assertEqual(h.data['rest_export_normal_limit_w'],10000)
  self.assertTrue(await h.set_export_limit(0,expected_limit=100));self.assertEqual(h._normal_export_limit_w,10000)
 async def test_saved_baseline_survives_startup_at_temporary_limit(self):
  h=hub(100,normal=7000);await h._refresh_rest_export_limit();self.assertEqual(h._normal_export_limit_w,7000)
  await h.set_export_limit(0,expected_limit=100);self.assertEqual(h._rest_client.writes,[0])
 async def test_first_native_normal_value_is_captured(self):
  h=hub(7000,normal=None);await h._refresh_rest_export_limit();self.assertEqual(h._normal_export_limit_w,7000)
 async def test_zero_startup_uses_existing_reference_fallback(self):
  h=hub(0,normal=None);await h._refresh_rest_export_limit();self.assertEqual(h._normal_export_limit_w,10000)
 async def test_no_export_above_normal_or_invalid_values(self):
  h=hub(normal=5000)
  for n in [-1,5001,True,1.5,float('nan')]:
   with self.assertRaises(ValueError):await h.set_export_limit(n)
  self.assertEqual(h._rest_client.writes,[])
 async def test_newer_external_setting_is_not_overwritten(self):
  h=hub(5000);self.assertFalse(await h.set_export_limit(0,expected_limit=100));self.assertEqual(h._rest_client.writes,[])
 async def test_unavailable_control_cannot_write(self):
  h=hub();h.rest_export_control_configured=False
  with self.assertRaises(RuntimeError):await h.set_export_limit(100)
  self.assertEqual(h._rest_client.writes,[])
class ActionTests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.h=hub();self.entry=types.SimpleNamespace(domain='fronius_modbus',state='loaded',runtime_data=self.h,options={'normal_export_limit_w':10000})
  def update(e,options):e.options=options
  manager=types.SimpleNamespace(async_get_entry=lambda _:self.entry,async_update_entry=Mock(side_effect=update))
  self.hass=types.SimpleNamespace(config_entries=manager)
  fake_asyncio=types.SimpleNamespace(sleep=AsyncMock())
  g=functions('__init__.py',{'set_export_limit'},{'hass':self.hass,'DOMAIN':'fronius_modbus','ConfigEntryState':types.SimpleNamespace(LOADED='loaded'),'HomeAssistantError':RuntimeError,'asyncio':fake_asyncio})
  self.action=g['set_export_limit'];self.sleep=fake_asyncio.sleep
 async def test_normal_test_restores_zero_and_clears_persisted_marker(self):
  await self.action(types.SimpleNamespace(data={'entry_id':'test','watts':100,'restore_after':60}))
  self.assertEqual(self.h._rest_client.writes,[100,0]);self.assertNotIn('export_limit_restore',self.entry.options)
  self.assertEqual(self.entry.options['normal_export_limit_w'],10000)
 async def test_pending_marker_is_written_before_command(self):
  original=self.h.set_export_limit
  async def command(*args,**kwargs):
   self.assertIn('export_limit_restore',self.entry.options);return await original(*args,**kwargs)
  self.h.set_export_limit=command
  await self.action(types.SimpleNamespace(data={'entry_id':'test','watts':100,'restore_after':60}))
 async def test_cancellation_still_restores_zero(self):
  self.sleep.side_effect=asyncio.CancelledError()
  with self.assertRaises(asyncio.CancelledError):await self.action(types.SimpleNamespace(data={'entry_id':'test','watts':100,'restore_after':60}))
  self.assertEqual(self.h._rest_client.writes,[100,0]);self.assertNotIn('export_limit_restore',self.entry.options)
 async def test_external_positive_price_command_wins(self):
  async def sleep(_):self.h._rest_client.limit=10000
  self.sleep.side_effect=sleep
  await self.action(types.SimpleNamespace(data={'entry_id':'test','watts':100,'restore_after':60}))
  self.assertEqual(self.h._rest_client.limit,10000);self.assertNotIn('export_limit_restore',self.entry.options)
 async def test_failed_restore_retains_pending_marker(self):
  original=self.h.set_export_limit
  async def command(watts,**kwargs):
   if watts==0:raise RuntimeError('link lost')
   return await original(watts,**kwargs)
  self.h.set_export_limit=command
  with self.assertRaises(RuntimeError):await self.action(types.SimpleNamespace(data={'entry_id':'test','watts':100,'restore_after':60}))
  self.assertEqual(self.entry.options['export_limit_restore'],{'watts':100,'restore':0})
 async def test_no_bounded_probe_can_replace_an_existing_normal_setting(self):
  self.h._rest_client.limit=10000
  with self.assertRaises(RuntimeError):await self.action(types.SimpleNamespace(data={'entry_id':'test','watts':100,'restore_after':60}))
  self.assertEqual(self.h._rest_client.writes,[]);self.assertNotIn('export_limit_restore',self.entry.options)
 async def test_test_cannot_claim_someone_elses_existing_100w_setting(self):
  self.h._rest_client.limit=100
  with self.assertRaises(RuntimeError):await self.action(types.SimpleNamespace(data={'entry_id':'test','watts':100,'restore_after':60}))
  self.assertEqual(self.h._rest_client.writes,[]);self.assertEqual(self.h._rest_client.limit,100)
 async def test_duplicate_test_rejected(self):
  self.entry.options['export_limit_restore']={'watts':100,'restore':0}
  with self.assertRaises(RuntimeError):await self.action(types.SimpleNamespace(data={'entry_id':'test','watts':100,'restore_after':60}))
  self.assertEqual(self.h._rest_client.writes,[])
class StartupTests(unittest.IsolatedAsyncioTestCase):
 async def setup_recovery(self,limit,normal=7000,marker=None):
  h=hub(limit,normal=None);h.init_data=h._refresh_rest_export_limit
  e=types.SimpleNamespace(runtime_data=h,options={'normal_export_limit_w':normal,**({'export_limit_restore':marker} if marker else {})})
  def update(e,options):e.options=options
  manager=types.SimpleNamespace(async_update_entry=Mock(side_effect=update));hass=types.SimpleNamespace(config_entries=manager)
  tree=ast.parse((ROOT/'__init__.py').read_text());f=next(n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='async_setup_entry')
  start=next(i for i,n in enumerate(f.body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='normal' for t in n.targets))
  end=next(i for i in range(start,len(f.body)) if isinstance(f.body[i],ast.Expr) and isinstance(f.body[i].value,ast.Await) and isinstance(f.body[i].value.value,ast.Call) and isinstance(f.body[i].value.value.func,ast.Attribute) and f.body[i].value.value.func.attr=='async_forward_entry_setups')
  f.name='recover';f.body=f.body[start:end];f.decorator_list=[]
  g={'hass':hass,'entry':e};exec(compile(ast.fix_missing_locations(ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),f],type_ignores=[])),'startup','exec'),g)
  await g['recover'](hass,e);return h,e
 async def test_pending_100w_restores_zero_after_ha_restart(self):
  h,e=await self.setup_recovery(100,marker={'watts':100,'restore':0})
  self.assertEqual(h._rest_client.limit,0);self.assertEqual(h._normal_export_limit_w,7000);self.assertNotIn('export_limit_restore',e.options)
 async def test_restart_preserves_newer_normal_command(self):
  h,e=await self.setup_recovery(7000,marker={'watts':100,'restore':0})
  self.assertEqual(h._rest_client.writes,[]);self.assertEqual(h._rest_client.limit,7000);self.assertNotIn('export_limit_restore',e.options)
 async def test_failed_restart_restore_keeps_marker(self):
  original=Wire.async_set_soft_export_limit
  async def fail(self,watts):raise RuntimeError('unavailable')
  with patch.object(Wire,'async_set_soft_export_limit',fail):
   with self.assertRaises(RuntimeError):await self.setup_recovery(100,marker={'watts':100,'restore':0})

if __name__=='__main__':unittest.main()
