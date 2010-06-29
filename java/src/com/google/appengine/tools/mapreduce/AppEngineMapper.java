/*
 * Copyright 2010 Google Inc.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package com.google.appengine.tools.mapreduce;

import com.google.appengine.api.datastore.DatastoreServiceFactory;

import org.apache.hadoop.conf.Configuration;
import org.apache.hadoop.mapreduce.Mapper;
import org.apache.hadoop.mapreduce.InputSplit;
import org.apache.hadoop.mapreduce.OutputCommitter;
import org.apache.hadoop.mapreduce.RecordReader;
import org.apache.hadoop.mapreduce.RecordWriter;
import org.apache.hadoop.mapreduce.StatusReporter;
import org.apache.hadoop.mapreduce.TaskAttemptID;

import java.io.IOException;

/**
 * An AppEngineMapper is a Hadoop Mapper that is run via a sequential
 * series of task queue executions.
 * 
 * <p>As such, the  {@link #run(org.apache.hadoop.mapreduce.Mapper.Context)}
 * method is unusable (since task state doesn't persist from one queue iteration
 * to the next).
 * 
 * <p>Additionally, the {@link Mapper} interface is extended with two methods
 * that get executed with each task queue invocation: 
 * {@link #taskSetup(org.apache.hadoop.Mapper.Context)} and 
 * {@link #taskCleanup(org.apache.hadoop.Mapper.Context)}. 
 *
 * <p>The {@link Context} object that is passed to each of the AppEngineMapper
 * methods is actually an {@link AppEngineContext} object. Therefore, you can
 * access an automatically flushed {@link DatastoreMutationPool} via the
 * {@link AppEngineContext#getMutationPool()} method. Note: For the automatic
 * flushing behavior, you must call
 * {@link #taskCleanup(org.apache.hadoop.Mapper.Context)} if you redefine that
 * method in a subclass.
 *
 * @author frew@google.com (Fred Wulff)
 */
public abstract class AppEngineMapper<KEYIN,VALUEIN,KEYOUT,VALUEOUT> 
    extends Mapper<KEYIN,VALUEIN,KEYOUT,VALUEOUT> {

  /**
   * A Context that holds a datastore mutation pool.
   */
  public class AppEngineContext extends Mapper<KEYIN,VALUEIN,KEYOUT,VALUEOUT>.Context {
    private DatastoreMutationPool mutationPool;

    public AppEngineContext(Configuration conf,
                            TaskAttemptID taskid,
                            RecordReader<KEYIN, VALUEIN> reader,
                            RecordWriter<KEYOUT, VALUEOUT> writer,
                            OutputCommitter committer,
                            StatusReporter reporter,
                            InputSplit split) throws IOException, InterruptedException {
      super(conf, taskid, reader, writer, committer, reporter, split);
    }

    public DatastoreMutationPool getMutationPool() {
      if (mutationPool == null) {
        mutationPool = new DatastoreMutationPool(DatastoreServiceFactory.getDatastoreService());
      }
      return mutationPool;
    }

    public void flush() {
      if (mutationPool != null) {
        mutationPool.flush();
      }
    }
  }
  
  /**
   * App Engine mappers have no {@code run(Context)} method, since it would
   * have to span multiple task queue invocations. Therefore, calling this
   * method always throws {@link java.lang.UnsupportedOperationException}.
   * 
   * @throws UnsupportedOperationException always
   */
  @Override
  public final void run(Context context) {
    throw new UnsupportedOperationException("AppEngineMappers don't have run methods");
  }
  
  @Override
  public void setup(Context context) throws IOException, InterruptedException {
    super.setup(context);
    // Nothing
  }
  
  /**
   * Run at the start of each task queue invocation.
   */
  public void taskSetup(Context context) throws IOException, InterruptedException {
    // Nothing
  }
  
  @Override
  public void cleanup(Context context) throws IOException, InterruptedException {
    super.cleanup(context);
    // Nothing
  }
  
  /**
   * Run at the end of each task queue invocation. The default flushes the context.
   */
  public void taskCleanup(Context context) throws IOException, InterruptedException {
    // We're the only client of this method, so we know that it will really be
    // an AppEngineContext, although we don't expose this to subclasses for simplicity.
    ((AppEngineContext) context).flush();
  }
  
  @Override
  public void map(KEYIN key, VALUEIN value, Context context) 
      throws IOException, InterruptedException {
    // Nothing (super does the identity map function, which is a bad idea since
    // we don't support shuffle/reduce yet).
  }
}
