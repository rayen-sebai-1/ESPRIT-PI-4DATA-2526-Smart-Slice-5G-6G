import { FormEvent, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import {
  KeyRound,
  Pencil,
  Power,
  Trash2,
  UserPlus,
  X,
} from "lucide-react";

import { createUser, deleteUser, getUsers, updateUser } from "@/api/authApi";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useAuth } from "@/hooks/useAuth";
import { usePageTitle } from "@/hooks/usePageTitle";
import { assignableRoleOptions, roleLabels } from "@/lib/constants";
import type {
  AdminCreateUserPayload,
  AdminUpdateUserPayload,
  AssignableRole,
  User,
  UserRole,
} from "@/types/auth";

const USERS_QUERY_KEY = ["admin", "users"] as const;

const initialForm: AdminCreateUserPayload = {
  full_name: "",
  email: "",
  password: "",
  role: "NETWORK_OPERATOR",
};

type ActorRole = "ADMIN" | "NETWORK_OPERATOR" | "DATA_MLOPS_ENGINEER";

function isManagerAdminRole(role: UserRole): role is "ADMIN" | "NETWORK_MANAGER" {
  return role === "ADMIN" || role === "NETWORK_MANAGER";
}

function extractErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    return String(error.response?.data?.detail ?? error.message ?? fallback);
  }
  if (error instanceof Error) {
    return error.message;
  }
  return fallback;
}

function RoleBadge({ role }: { role: UserRole }) {
  const tone =
    isManagerAdminRole(role)
      ? "border-red-500/30 bg-red-500/10 text-red-200"
      : role === "DATA_MLOPS_ENGINEER"
        ? "border-violet-400/30 bg-violet-400/10 text-violet-100"
        : "border-sky-400/30 bg-sky-400/10 text-sky-100";
  return (
    <span className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-medium ${tone}`}>
      {roleLabels[role]}
    </span>
  );
}

export function UsersManagementPage() {
  usePageTitle("User management");

  const queryClient = useQueryClient();
  const { user: currentUser } = useAuth();
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [form, setForm] = useState<AdminCreateUserPayload>(initialForm);
  const [formError, setFormError] = useState<string | null>(null);

  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [editForm, setEditForm] = useState<AdminUpdateUserPayload>({});
  const [editError, setEditError] = useState<string | null>(null);

  const [resetPasswordFor, setResetPasswordFor] = useState<User | null>(null);
  const [newPassword, setNewPassword] = useState("");
  const [resetError, setResetError] = useState<string | null>(null);

  const usersQuery = useQuery({
    queryKey: USERS_QUERY_KEY,
    queryFn: getUsers,
  });

  const createMutation = useMutation({
    mutationFn: (payload: AdminCreateUserPayload) => createUser(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: USERS_QUERY_KEY });
      setForm(initialForm);
      setIsFormOpen(false);
      setFormError(null);
    },
    onError: (error) => {
      setFormError(extractErrorMessage(error, "Creation failed."));
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: AdminUpdateUserPayload }) =>
      updateUser(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: USERS_QUERY_KEY });
      setEditingUser(null);
      setEditForm({});
      setEditError(null);
      setResetPasswordFor(null);
      setNewPassword("");
      setResetError(null);
    },
    onError: (error) => {
      const message = extractErrorMessage(error, "Update failed.");
      if (resetPasswordFor) {
        setResetError(message);
      } else {
        setEditError(message);
      }
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteUser(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: USERS_QUERY_KEY });
    },
  });

  const users = usersQuery.data ?? [];

  const totalsByRole = useMemo(() => {
    const counts: Record<ActorRole, number> = {
      ADMIN: 0,
      NETWORK_OPERATOR: 0,
      DATA_MLOPS_ENGINEER: 0,
    };
    for (const user of users) {
      if (isManagerAdminRole(user.role)) {
        counts.ADMIN += 1;
      } else {
        counts[user.role] += 1;
      }
    }
    return counts;
  }, [users]);

  function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    if (form.password.length < 8) {
      setFormError("Password must contain at least 8 characters.");
      return;
    }
    if (form.full_name.trim().length < 3) {
      setFormError("Full name must contain at least 3 characters.");
      return;
    }
    createMutation.mutate(form);
  }

  function openEdit(user: User) {
    setEditingUser(user);
    setEditForm({
      full_name: user.full_name,
      role: isManagerAdminRole(user.role) ? undefined : (user.role as AssignableRole),
    });
    setEditError(null);
  }

  function handleEditSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editingUser) return;
    const payload: AdminUpdateUserPayload = {};
    if (editForm.full_name !== undefined && editForm.full_name !== editingUser.full_name) {
      payload.full_name = editForm.full_name;
    }
    if (editForm.role !== undefined && editForm.role !== editingUser.role) {
      payload.role = editForm.role;
    }
    if (Object.keys(payload).length === 0) {
      setEditingUser(null);
      return;
    }
    updateMutation.mutate({ id: editingUser.id, payload });
  }

  function handleToggleActive(user: User) {
    if (isManagerAdminRole(user.role)) return;
    updateMutation.mutate({ id: user.id, payload: { is_active: !user.is_active } });
  }

  function handleResetPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!resetPasswordFor) return;
    if (newPassword.length < 8) {
      setResetError("Password must contain at least 8 characters.");
      return;
    }
    updateMutation.mutate({
      id: resetPasswordFor.id,
      payload: { password: newPassword },
    });
  }

  function handleDelete(user: User) {
    if (isManagerAdminRole(user.role)) return;
    if (currentUser?.id === user.id) return;
    const confirmed = window.confirm(
      `Remove the account for ${user.full_name} (${user.email})? The user will be disabled and kept in audit logs.`,
    );
    if (!confirmed) return;
    deleteMutation.mutate(user.id);
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Admin console"
        title="User management"
        description="Provision platform access for NOC Operators and MLOps Engineers. Manager (Admin) accounts are protected in this interface."
        actions={
          <Button
            type="button"
            onClick={() => {
              setIsFormOpen((value) => !value);
              setFormError(null);
            }}
          >
            {isFormOpen ? (
              <>
                <X size={16} />
                Close form
              </>
            ) : (
              <>
                <UserPlus size={16} />
                New user
              </>
            )}
          </Button>
        }
      />

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {(Object.keys(totalsByRole) as ActorRole[]).map((role) => (
          <Card key={role} className="p-5">
            <p className="text-xs uppercase tracking-[0.24em] text-mutedText">{roleLabels[role]}</p>
            <p className="mt-3 text-3xl font-semibold text-white">{totalsByRole[role]}</p>
            <p className="mt-2 text-xs text-mutedText">
              {role === "ADMIN"
                ? "Managers with full administrator visibility"
                : role === "NETWORK_OPERATOR"
                  ? "NOC in operational supervision"
                  : "MLOps focused on models and pipelines"}
            </p>
          </Card>
        ))}
      </section>

      {isFormOpen ? (
        <Card className="p-6">
          <h3 className="text-lg font-semibold text-white">Create a new account</h3>
          <p className="mt-2 text-sm text-mutedText">
            The user can sign in immediately with the email and password you enter.
            You can change the password later via "Reset".
          </p>
          <form className="mt-5 grid gap-4 md:grid-cols-2" onSubmit={handleCreate}>
            <div>
              <label className="mb-2 block text-sm text-slate-200" htmlFor="new_full_name">
                Full name
              </label>
              <Input
                id="new_full_name"
                value={form.full_name}
                onChange={(event) => setForm((prev) => ({ ...prev, full_name: event.target.value }))}
                required
              />
            </div>
            <div>
              <label className="mb-2 block text-sm text-slate-200" htmlFor="new_email">
                Email
              </label>
              <Input
                id="new_email"
                type="email"
                value={form.email}
                onChange={(event) => setForm((prev) => ({ ...prev, email: event.target.value }))}
                required
              />
            </div>
            <div>
              <label className="mb-2 block text-sm text-slate-200" htmlFor="new_role">
                Role
              </label>
              <Select
                id="new_role"
                value={form.role}
                onChange={(event) =>
                  setForm((prev) => ({ ...prev, role: event.target.value as AssignableRole }))
                }
              >
                {assignableRoleOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <label className="mb-2 block text-sm text-slate-200" htmlFor="new_password">
                Initial password
              </label>
              <Input
                id="new_password"
                type="text"
                value={form.password}
                onChange={(event) => setForm((prev) => ({ ...prev, password: event.target.value }))}
                required
                minLength={6}
              />
            </div>
            {formError ? (
              <div className="rounded-2xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-200 md:col-span-2">
                {formError}
              </div>
            ) : null}
            <div className="flex gap-3 md:col-span-2">
              <Button type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending ? "Creating..." : "Create account"}
              </Button>
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  setForm(initialForm);
                  setIsFormOpen(false);
                  setFormError(null);
                }}
              >
                Cancel
              </Button>
            </div>
          </form>
        </Card>
      ) : null}

      <Card className="p-0">
        <div className="border-b border-white/5 p-5">
          <h3 className="text-lg font-semibold text-white">Provisioned accounts</h3>
          <p className="mt-1 text-sm text-mutedText">
            {users.length} account(s) registered on the platform.
          </p>
        </div>

        {usersQuery.isLoading ? (
          <div className="p-6 text-sm text-mutedText">Loading users...</div>
        ) : usersQuery.isError ? (
          <EmptyState
            title="List unavailable"
            description="Unable to retrieve users. Check that the auth API is running."
          />
        ) : users.length === 0 ? (
          <EmptyState
            title="No user"
            description="Create the first account using the 'New user' button."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead>
                <tr className="border-b border-white/5 text-xs uppercase tracking-[0.18em] text-mutedText">
                  <th className="px-5 py-4">User</th>
                  <th className="px-5 py-4">Role</th>
                  <th className="px-5 py-4">Status</th>
                  <th className="px-5 py-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => {
                  const isSelf = currentUser?.id === user.id;
                  const isAdminRow = isManagerAdminRole(user.role);
                  return (
                    <tr
                      key={user.id}
                      className="border-b border-white/5 text-slate-200 last:border-b-0"
                    >
                      <td className="px-5 py-4">
                        <div className="font-medium text-white">{user.full_name}</div>
                        <div className="text-xs text-mutedText">{user.email}</div>
                      </td>
                      <td className="px-5 py-4">
                        <RoleBadge role={user.role} />
                      </td>
                      <td className="px-5 py-4">
                        <span
                          className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs ${
                            user.is_active
                              ? "border-emerald-400/30 bg-emerald-400/10 text-emerald-200"
                              : "border-slate-500/30 bg-slate-500/10 text-slate-300"
                          }`}
                        >
                          <span
                            className={`h-1.5 w-1.5 rounded-full ${
                              user.is_active ? "bg-emerald-300" : "bg-slate-400"
                            }`}
                          />
                          {user.is_active ? "Active" : "Disabled"}
                        </span>
                      </td>
                      <td className="px-5 py-4">
                        <div className="flex flex-wrap justify-end gap-2">
                          <Button
                            type="button"
                            variant="secondary"
                            size="sm"
                            onClick={() => openEdit(user)}
                            disabled={isAdminRow}
                            title={isAdminRow ? "Manager/Admin profile is protected" : "Edit"}
                          >
                            <Pencil size={14} />
                            Edit
                          </Button>
                          <Button
                            type="button"
                            variant="secondary"
                            size="sm"
                            onClick={() => {
                              setResetPasswordFor(user);
                              setNewPassword("");
                              setResetError(null);
                            }}
                          >
                            <KeyRound size={14} />
                            Reset
                          </Button>
                          <Button
                            type="button"
                            variant="secondary"
                            size="sm"
                            onClick={() => handleToggleActive(user)}
                            disabled={isAdminRow || isSelf}
                            title={
                              isAdminRow
                                ? "A Manager/Admin account cannot be disabled"
                                : user.is_active
                                  ? "Disable account"
                                  : "Re-enable account"
                            }
                          >
                            <Power size={14} />
                            {user.is_active ? "Disable" : "Re-enable"}
                          </Button>
                          <Button
                            type="button"
                            variant="danger"
                            size="sm"
                            onClick={() => handleDelete(user)}
                            disabled={isAdminRow || isSelf}
                            title={
                              isAdminRow
                                ? "A Manager/Admin account cannot be deleted"
                                : isSelf
                                  ? "You cannot delete your own account"
                                  : "Delete"
                            }
                          >
                            <Trash2 size={14} />
                            Delete
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {editingUser ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 px-4 backdrop-blur-sm"
          role="dialog"
          aria-modal
        >
          <Card className="w-full max-w-lg p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs uppercase tracking-[0.24em] text-mutedText">Edit</p>
                <h3 className="mt-2 text-lg font-semibold text-white">{editingUser.email}</h3>
              </div>
              <button
                type="button"
                className="rounded-full border border-border bg-cardAlt/80 p-2 text-slate-200 transition hover:border-accent/40"
                onClick={() => {
                  setEditingUser(null);
                  setEditError(null);
                }}
              >
                <X size={16} />
              </button>
            </div>
            <form className="mt-5 space-y-4" onSubmit={handleEditSubmit}>
              <div>
                <label className="mb-2 block text-sm text-slate-200" htmlFor="edit_full_name">
                  Full name
                </label>
                <Input
                  id="edit_full_name"
                  value={editForm.full_name ?? ""}
                  onChange={(event) =>
                    setEditForm((prev) => ({ ...prev, full_name: event.target.value }))
                  }
                  required
                />
              </div>
              <div>
                <label className="mb-2 block text-sm text-slate-200" htmlFor="edit_role">
                  Role
                </label>
                <Select
                  id="edit_role"
                  value={editForm.role ?? (editingUser.role as AssignableRole)}
                  onChange={(event) =>
                    setEditForm((prev) => ({
                      ...prev,
                      role: event.target.value as AssignableRole,
                    }))
                  }
                >
                  {assignableRoleOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </Select>
              </div>
              {editError ? (
                <div className="rounded-2xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-200">
                  {editError}
                </div>
              ) : null}
              <div className="flex gap-3">
                <Button type="submit" disabled={updateMutation.isPending}>
                  {updateMutation.isPending ? "Saving..." : "Save"}
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => {
                    setEditingUser(null);
                    setEditError(null);
                  }}
                >
                  Cancel
                </Button>
              </div>
            </form>
          </Card>
        </div>
      ) : null}

      {resetPasswordFor ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 px-4 backdrop-blur-sm"
          role="dialog"
          aria-modal
        >
          <Card className="w-full max-w-md p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs uppercase tracking-[0.24em] text-mutedText">
                  Reset password
                </p>
                <h3 className="mt-2 text-lg font-semibold text-white">
                  {resetPasswordFor.email}
                </h3>
                <p className="mt-2 text-sm text-mutedText">
                  The new password replaces the current one. Share it securely with
                  the user.
                </p>
              </div>
              <button
                type="button"
                className="rounded-full border border-border bg-cardAlt/80 p-2 text-slate-200 transition hover:border-accent/40"
                onClick={() => {
                  setResetPasswordFor(null);
                  setResetError(null);
                }}
              >
                <X size={16} />
              </button>
            </div>
            <form className="mt-5 space-y-4" onSubmit={handleResetPassword}>
              <div>
                <label className="mb-2 block text-sm text-slate-200" htmlFor="reset_password">
                  New password
                </label>
                <Input
                  id="reset_password"
                  type="text"
                  value={newPassword}
                  onChange={(event) => setNewPassword(event.target.value)}
                  minLength={6}
                  required
                />
              </div>
              {resetError ? (
                <div className="rounded-2xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-200">
                  {resetError}
                </div>
              ) : null}
              <div className="flex gap-3">
                <Button type="submit" disabled={updateMutation.isPending}>
                  {updateMutation.isPending ? "Updating..." : "Confirm"}
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => {
                    setResetPasswordFor(null);
                    setResetError(null);
                  }}
                >
                  Cancel
                </Button>
              </div>
            </form>
          </Card>
        </div>
      ) : null}
    </div>
  );
}
