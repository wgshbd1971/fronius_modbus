import asyncio,importlib.util,sys,types,unittest
from pathlib import Path
from unittest.mock import AsyncMock,patch
ROOT=Path(__file__).resolve().parents[1]/'custom_components/fronius_modbus'
def load(name):
 spec=importlib.util.spec_from_file_location('fronius_ownership_test.'+name,ROOT/(name+'.py'));m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m);return m
pkg=types.ModuleType('fronius_ownership_test');pkg.__path__=[str(ROOT)];sys.modules[pkg.__name__]=pkg
p=load('storage_control');rest=load('froniusrestclient')
class StorageTests(unittest.TestCase):
 def test_external_auto_change_replaces_old_block_label(self):self.assertEqual(p.observed_storage_mode(0,10000,10000,6),0)
 def test_same_bits_but_changed_rate_replaces_old_block_label(self):self.assertEqual(p.observed_storage_mode(3,10000,10000,6),3)
 def test_actual_zero_discharge_and_forced_modes(self):
  for args,want in [((3,10000,0),6),((2,10000,-5000),4),((1,-5000,10000),5),((3,0,10000),7),((9,0,0),None)]:self.assertEqual(p.observed_storage_mode(*args),want)
 def test_zero_power_grid_intent_is_retained_only_for_matching_registers(self):
  self.assertEqual(p.observed_storage_mode(2,10000,0,4),4);self.assertEqual(p.observed_storage_mode(3,10000,0,4),6)
class RestTests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.c=rest.FroniusRestClient(None,'example.invalid','unused','unused');self.before=dict(enableRemoteControl=True,customerRemoteControlProfileActive=True,technicianRemoteControlProfileActive=True)
 async def invoke(self,key,enabled,other_change=False):
  after=self.before.copy();after[key]=enabled
  if other_change:after['technicianRemoteControlProfileActive']=False
  self.c.async_get_remote_control=AsyncMock(side_effect=[self.before,after]);self.c._request=AsyncMock(return_value={'writeSuccess':[key]})
  with patch.object(rest.asyncio,'sleep',new=AsyncMock()):return await self.c._set_cloud_flag(key,enabled)
 async def test_optional_vpp_disable_preserves_master_and_regulatory(self):
  after=await self.invoke('customerRemoteControlProfileActive',False)
  self.c._request.assert_awaited_once_with('POST',rest.SOLARWEB_PATH,{'customerRemoteControlProfileActive':False})
  self.assertTrue(after['technicianRemoteControlProfileActive']);self.assertTrue(after['enableRemoteControl'])
 async def test_master_enable_never_reenables_vpp(self):
  self.before.update(enableRemoteControl=False,customerRemoteControlProfileActive=False)
  after=await self.invoke('enableRemoteControl',True);self.assertFalse(after['customerRemoteControlProfileActive'])
  self.c._request.assert_awaited_once_with('POST',rest.SOLARWEB_PATH,{'enableRemoteControl':True})
 async def test_regulatory_profile_prevents_master_disable(self):
  self.c.async_get_remote_control=AsyncMock(return_value=self.before);self.c._request=AsyncMock()
  with self.assertRaises(rest.FroniusRestError):await self.c.async_set_remote_control_enabled(False)
  self.c._request.assert_not_awaited()
 async def test_unrelated_profile_change_is_not_reported_as_success(self):
  with self.assertRaises(rest.FroniusRestError):await self.invoke('customerRemoteControlProfileActive',False,True)
 async def test_unconfirmed_cloud_write_is_an_error(self):
  self.c.async_get_remote_control=AsyncMock(return_value=self.before);self.c._request=AsyncMock(return_value={'writeFailure':['customerRemoteControlProfileActive']})
  with self.assertRaises(rest.FroniusRestError):await self.c.async_set_customer_profile_enabled(False)
class PollTests(unittest.IsolatedAsyncioTestCase):
 async def test_storage_poll_updates_mode_and_rates_on_every_read(self):
  fake=types.ModuleType('fronius_ownership_test.extmodbusclient')
  class Base:
   def calculate_value(self,value,sf,*args):return value*10**sf
  fake.ExtModbusClient=Base
  with patch.dict(sys.modules,{'fronius_ownership_test.extmodbusclient':fake,'requests':types.ModuleType('requests')}):clientmod=load('froniusmodbusclient')
  client=object.__new__(clientmod.FroniusModbusClient);client._inverter_unit_id=1;client.storage_extended_control_mode=6;client.data={'ext_control_mode':'Block Discharging','control_mode':'Change and Discharge'}
  class Wire:
   DATATYPE=types.SimpleNamespace(UINT16='u',INT16='i')
   def convert_from_registers(self,r,data_type):return r[0]-65536 if data_type=='i' and r[0]>32767 else r[0]
  client._client=Wire();regs=[0]*24;regs[0]=11000;regs[3]=0;regs[6]=9300;regs[9]=6;regs[10]=10000;regs[11]=10000
  client.get_registers=AsyncMock(return_value=regs)
  await client.read_inverter_storage_data();self.assertEqual(client.data['ext_control_mode'],'Auto');self.assertEqual(client.data['discharge_limit'],100)
  regs[3]=3;regs[10]=0;await client.read_inverter_storage_data();self.assertEqual(client.data['ext_control_mode'],'Block Discharging');self.assertEqual(client.data['storage_mode_raw'],3)
  regs[10]=10000;await client.read_inverter_storage_data();self.assertEqual(client.data['ext_control_mode'],'PV Charge and Discharge Limit');self.assertEqual(client.data['discharge_limit'],100)
if __name__=='__main__':unittest.main()
