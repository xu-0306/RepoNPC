export interface AdminSessionBody {
  csrf_token: string;
  expires_at: string;
  absolute_expires_at: string;
}

export interface AdminAuthMethodsBody {
  mode: "local_launch" | "password";
  password: { available: boolean };
  setup_required: boolean;
}

export async function restoreExistingAdminSession(
  loadMethods: () => Promise<AdminAuthMethodsBody>,
  resumeSession: () => Promise<AdminSessionBody>,
): Promise<{
  methods: AdminAuthMethodsBody;
  session: AdminSessionBody | null;
}> {
  const methods = await loadMethods();
  try {
    return { methods, session: await resumeSession() };
  } catch {
    return { methods, session: null };
  }
}
