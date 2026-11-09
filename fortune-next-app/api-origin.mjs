export const TEACHER_SURFACE = "teacher";
// This literal is inlined by Next for a dedicated build; runtime omission
// must not turn that build into the ordinary doctor's default deployment.
const teacherBuild = process.env.FORTUNE_READING_BUILD_MODE === TEACHER_SURFACE;

export function teacherUiEnabled(env = process.env) {
  return teacherBuild || env.FORTUNE_UI_SURFACE === "teacher" || Boolean(env.FORTUNE_REQUIRED_DEPLOYMENT_SURFACE);
}

export function apiOrigin(env = process.env, forceTeacher = false) {
  if (!forceTeacher && !teacherUiEnabled(env)) {
    return env.FORTUNE_API_ORIGIN || "http://127.0.0.1:8765";
  }
  const value = env.FORTUNE_API_ORIGIN;
  if (env.FORTUNE_UI_SURFACE !== "teacher" || !value ||
      (env.FORTUNE_REQUIRED_DEPLOYMENT_SURFACE && env.FORTUNE_REQUIRED_DEPLOYMENT_SURFACE !== TEACHER_SURFACE)) {
    throw new Error("Teacher API connection must be explicitly configured.");
  }
  // A dedicated teacher build must never forward a Cookie to another surface.
  if (value !== "http://127.0.0.1:8773" && value !== "http://127.0.0.1:8773/") {
    throw new Error("Teacher API connection is not the dedicated loopback endpoint.");
  }
  return "http://127.0.0.1:8773";
}
