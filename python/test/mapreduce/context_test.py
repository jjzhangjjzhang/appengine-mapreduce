#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""Tests for google.appengine.ext.mapreduce.context."""


import google

from testlib import mox
import os

import unittest
from google.appengine.api import datastore
from google.appengine.ext import db
from mapreduce import context


class TestEntity(db.Model):
  """Test entity class to test db operations."""

  tag = db.TextProperty()


def new_datastore_entity(key_name=None):
  return datastore.Entity('TestEntity', name=key_name)


class ItemListTest(unittest.TestCase):
  """Tests for context.ItemList class."""

  def setUp(self):
    self.list = context.ItemList()

  def testAppend(self):
    """Test append method."""
    self.assertEquals([], self.list.items)
    self.assertEquals(0, self.list.size)

    self.list.append('abc', 100)

    self.assertEquals(['abc'], self.list.items)
    self.assertEquals(100, self.list.size)

  def testClear(self):
    """Test clear method."""
    self.list.append('abc', 100)
    self.assertEquals(['abc'], self.list.items)
    self.assertEquals(100, self.list.size)

    self.list.clear()

    self.assertEquals([], self.list.items)
    self.assertEquals(0, self.list.size)

  def testBackwardsCompat(self):
    """Old class name and 'entities' property should still work."""
    self.list = context.EntityList()
    self.list.append('abc', 100)
    self.assertEquals(['abc'], self.list.entities)
    self.assertEquals(self.list.items, self.list.entities)
    self.assertEquals(100, self.list.size)


class MutationPoolTest(unittest.TestCase):
  """Tests for context.MutationPool class."""

  def setUp(self):
    self.appid = 'testapp'
    os.environ['APPLICATION_ID'] = self.appid
    self.pool = context.MutationPool()

  def testPut(self):
    """Test put method."""
    e = TestEntity()
    self.pool.put(e)
    self.assertEquals([e._populate_internal_entity()], self.pool.puts.items)
    self.assertEquals([], self.pool.deletes.items)

  def testPutEntity(self):
    """Test put method using a datastore Entity directly."""
    e = new_datastore_entity()
    self.pool.put(e)
    self.assertEquals([e], self.pool.puts.items)
    self.assertEquals([], self.pool.deletes.items)
    e2 = TestEntity()
    self.pool.put(e2)
    self.assertEquals([e, e2._populate_internal_entity()], self.pool.puts.items)

  def testDelete(self):
    """Test delete method with a model instance"""
    e = TestEntity(key_name='goingaway')
    self.pool.delete(e)
    self.assertEquals([], self.pool.puts.items)
    self.assertEquals([e.key()], self.pool.deletes.items)

  def testDeleteEntity(self):
    """Test delete method with a datastore entity"""
    e = new_datastore_entity(key_name='goingaway')
    self.pool.delete(e)
    self.assertEquals([], self.pool.puts.items)
    self.assertEquals([e.key()], self.pool.deletes.items)

  def testDeleteKey(self):
    """Test delete method with a key instance."""
    k = db.Key.from_path('MyKind', 'MyKeyName', _app='myapp')
    self.pool.delete(k)
    self.assertEquals([], self.pool.puts.items)
    self.assertEquals([k], self.pool.deletes.items)
    self.pool.delete(str(k))
    self.assertEquals([k, k], self.pool.deletes.items)

  def testPutOverPoolSize(self):
    """Test putting more than pool size."""
    self.pool = context.MutationPool(1000)

    m = mox.Mox()
    m.StubOutWithMock(datastore, 'Put', use_mock_anything=True)

    e1 = TestEntity()
    e2 = TestEntity(tag=' ' * 1000)

    datastore.Put([e1._populate_internal_entity()])

    m.ReplayAll()
    try:
      self.pool.put(e1)
      self.assertEquals([e1._populate_internal_entity()], self.pool.puts.items)

      self.pool.put(e2)
      self.assertEquals([e2._populate_internal_entity()], self.pool.puts.items)

      m.VerifyAll()
    finally:
      m.UnsetStubs()

  def testPutTooManyEntities(self):
    """Test putting more than allowed entity count."""
    self.pool = context.MutationPool()

    m = mox.Mox()
    m.StubOutWithMock(datastore, 'Put', use_mock_anything=True)

    entities = []
    for i in range(context.MAX_ENTITY_COUNT + 50):
      entities.append(TestEntity())

    datastore.Put([e._populate_internal_entity()
                   for e in entities[:context.MAX_ENTITY_COUNT]])

    m.ReplayAll()
    try:
      for e in entities:
        self.pool.put(e)

      self.assertEquals(50, self.pool.puts.length)

      m.VerifyAll()
    finally:
      m.UnsetStubs()

  def testDeleteOverPoolSize(self):
    """Test deleting more than pool size."""
    self.pool = context.MutationPool(500)

    m = mox.Mox()
    m.StubOutWithMock(datastore, 'Delete', use_mock_anything=True)

    e1 = TestEntity(key_name='goingaway')
    e2 = TestEntity(key_name='x' * 500)

    datastore.Delete([e1.key()])

    m.ReplayAll()
    try:
      self.pool.delete(e1)
      self.assertEquals([e1.key()], self.pool.deletes.items)

      self.pool.delete(e2)
      self.assertEquals([e2.key()], self.pool.deletes.items)

      m.VerifyAll()
    finally:
      m.UnsetStubs()

  def testDeleteTooManyEntities(self):
    """Test putting more than allowed entity count."""
    self.pool = context.MutationPool()

    m = mox.Mox()
    m.StubOutWithMock(datastore, 'Delete', use_mock_anything=True)

    entities = []
    for i in range(context.MAX_ENTITY_COUNT + 50):
      entities.append(TestEntity(key_name='die%d' % i))

    datastore.Delete([e.key() for e in entities[:context.MAX_ENTITY_COUNT]])

    m.ReplayAll()
    try:
      for e in entities:
        self.pool.delete(e)

      self.assertEquals(50, self.pool.deletes.length)

      m.VerifyAll()
    finally:
      m.UnsetStubs()

  def testFlush(self):
    """Test flush method."""
    self.pool = context.MutationPool(1000)

    m = mox.Mox()
    m.StubOutWithMock(datastore, 'Delete', use_mock_anything=True)
    m.StubOutWithMock(datastore, 'Put', use_mock_anything=True)

    e1 = TestEntity()
    e2 = TestEntity(key_name='flushme')

    datastore.Put([e1._populate_internal_entity()])
    datastore.Delete([e2.key()])

    m.ReplayAll()
    try:
      self.pool.put(e1)
      self.assertEquals([e1._populate_internal_entity()], self.pool.puts.items)

      self.pool.delete(e2)
      self.assertEquals([e2.key()], self.pool.deletes.items)

      self.pool.flush()

      self.assertEquals([], self.pool.puts.items)
      self.assertEquals([], self.pool.deletes.items)

      m.VerifyAll()
    finally:
      m.UnsetStubs()


class CountersTest(unittest.TestCase):
  """Test for context.Counters class."""

  def testIncrement(self):
    """Test increment() method."""
    m = mox.Mox()

    shard_state = m.CreateMockAnything()
    counters_map = m.CreateMockAnything()
    shard_state.counters_map = counters_map
    counters = context.Counters(shard_state)

    counters_map.increment('test', 19)

    m.ReplayAll()
    try:
      counters.increment('test', 19)

      m.VerifyAll()
    finally:
      m.UnsetStubs()

  def testFlush(self):
    """Test flush() method."""
    counters = context.Counters(None)
    counters.flush()


class ContextTest(unittest.TestCase):
  """Test for context.Context class."""

  def testGetSetContext(self):
    """Test module's get_context and _set functions."""
    ctx = context.Context(None, None)
    self.assertFalse(context.get())
    context.Context._set(ctx)
    self.assertEquals(ctx, context.get())
    context.Context._set(None)
    self.assertEquals(None, context.get())

  def testArbitraryPool(self):
    """Test arbitrary pool registration."""
    m = mox.Mox()

    ctx = context.Context(None, None)
    self.assertFalse(ctx.get_pool("test"))
    pool = m.CreateMockAnything()
    ctx.register_pool("test", pool)
    self.assertEquals(pool, ctx.get_pool("test"))

    pool.flush()

    m.ReplayAll()
    try:
      ctx.flush()
      m.VerifyAll()
    finally:
      m.UnsetStubs()


if __name__ == "__main__":
  unittest.main()
