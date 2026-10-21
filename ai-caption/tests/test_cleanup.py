import asyncio
import sys
import unittest

from immivio_caption.pipeline import Pipeline


class ProcessCleanupTests(unittest.IsolatedAsyncioTestCase):
    async def test_killed_process_with_full_output_pipe_is_reaped(self):
        pipeline = Pipeline(None, None, None, "", 1, "/film.mp4", 0)
        pipeline.process = await asyncio.create_subprocess_exec(
            sys.executable, "-c",
            "import os,time; os.write(1,b'x'*10000000); time.sleep(60)",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        await asyncio.sleep(.15)
        await asyncio.wait_for(pipeline.close_process(), 3)
        self.assertIsNotNone(pipeline.process.returncode)
