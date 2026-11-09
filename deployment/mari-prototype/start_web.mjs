/** Dedicated wrapper; direct Next execution is additionally guarded by build/marker checks. */
import { spawn } from "node:child_process";
import { resolve, isAbsolute } from "node:path";
import { apiOrigin, TEACHER_SURFACE } from "../../fortune-next-app/api-origin.mjs";

try {
  apiOrigin(process.env, true);
  if (process.env.FORTUNE_REQUIRED_DEPLOYMENT_SURFACE !== TEACHER_SURFACE) throw new Error();
  const args = process.argv.slice(2);
  const build = args.includes("--build");
  const directory = args.indexOf("--app-dir");
  const app = directory >= 0 ? args[directory + 1] : "";
  const index = args.indexOf("--port");
  const port = index >= 0 ? Number(args[index + 1]) : 3012;
  if (!app || !isAbsolute(app) || !Number.isInteger(port) || port < 1024 || port > 65535) throw new Error();
  const child = spawn(process.execPath, [resolve(app, "node_modules/next/dist/bin/next"),
    ...(build ? ["build"] : ["start", "-H", "127.0.0.1", "-p", String(port)])],
    { cwd: app, env: process.env, stdio: "inherit", shell: false });
  for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => child.kill(signal));
  child.on("error", () => { process.stderr.write("Teacher Web could not start.\n"); process.exitCode = 1; });
  child.on("exit", code => { process.exitCode = code ?? 1; });
} catch {
  process.stderr.write("Teacher Web configuration is incomplete.\n");
  process.exitCode = 1;
}
