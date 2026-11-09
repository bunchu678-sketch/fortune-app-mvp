export const TEACHER_SURFACE: "teacher";
export function teacherUiEnabled(env?: Record<string, string | undefined>): boolean;
export function apiOrigin(env?: Record<string, string | undefined>, forceTeacher?: boolean): string;
