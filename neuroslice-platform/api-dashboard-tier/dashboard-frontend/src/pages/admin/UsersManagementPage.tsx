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
    role === "ADMIN"
      ? "border-red-500/30 bg-red-500/10 text-red-200"
      : role === "NETWORK_MANAGER"
        ? "border-amber-400/30 bg-amber-400/10 text-amber-100"
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
  usePageTitle("Gestion utilisateurs");

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
      setFormError(extractErrorMessage(error, "La creation a echoue."));
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
      const message = extractErrorMessage(error, "La mise a jour a echoue.");
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
    const counts: Record<UserRole, number> = {
      ADMIN: 0,
      NETWORK_OPERATOR: 0,
      NETWORK_MANAGER: 0,
      DATA_MLOPS_ENGINEER: 0,
    };
    for (const user of users) counts[user.role] += 1;
    return counts;
  }, [users]);

  function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    if (form.password.length < 6) {
      setFormError("Le mot de passe doit contenir au moins 6 caracteres.");
      return;
    }
    if (form.full_name.trim().length < 3) {
      setFormError("Le nom complet doit contenir au moins 3 caracteres.");
      return;
    }
    createMutation.mutate(form);
  }

  function openEdit(user: User) {
    setEditingUser(user);
    setEditForm({
      full_name: user.full_name,
      role: user.role === "ADMIN" ? undefined : (user.role as AssignableRole),
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
    if (user.role === "ADMIN") return;
    updateMutation.mutate({ id: user.id, payload: { is_active: !user.is_active } });
  }

  function handleResetPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!resetPasswordFor) return;
    if (newPassword.length < 6) {
      setResetError("Le mot de passe doit contenir au moins 6 caracteres.");
      return;
    }
    updateMutation.mutate({
      id: resetPasswordFor.id,
      payload: { password: newPassword },
    });
  }

  function handleDelete(user: User) {
    if (user.role === "ADMIN") return;
    if (currentUser?.id === user.id) return;
    const confirmed = window.confirm(
      `Supprimer definitivement le compte de ${user.full_name} (${user.email}) ?`,
    );
    if (!confirmed) return;
    deleteMutation.mutate(user.id);
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Admin console"
        title="Gestion des utilisateurs"
        description="Provisionne les acces a la plateforme : NOC, Manager reseau et Data / MLOps Engineer. Les administrateurs ne sont ni modifiables ni supprimables depuis cette interface."
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
                Fermer le formulaire
              </>
            ) : (
              <>
                <UserPlus size={16} />
                Nouvel utilisateur
              </>
            )}
          </Button>
        }
      />

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {(Object.keys(totalsByRole) as UserRole[]).map((role) => (
          <Card key={role} className="p-5">
            <p className="text-xs uppercase tracking-[0.24em] text-mutedText">{roleLabels[role]}</p>
            <p className="mt-3 text-3xl font-semibold text-white">{totalsByRole[role]}</p>
            <p className="mt-2 text-xs text-mutedText">
              {role === "ADMIN"
                ? "Administrateurs de la plateforme"
                : role === "NETWORK_OPERATOR"
                  ? "NOC en supervision operationnelle"
                  : role === "NETWORK_MANAGER"
                    ? "Managers avec vue strategique"
                    : "Data / MLOps orientes modeles & pipelines"}
            </p>
          </Card>
        ))}
      </section>

      {isFormOpen ? (
        <Card className="p-6">
          <h3 className="text-lg font-semibold text-white">Creer un nouveau compte</h3>
          <p className="mt-2 text-sm text-mutedText">
            L'utilisateur pourra se connecter immediatement avec l'email et le mot de passe que tu
            saisis. Tu peux changer le mot de passe plus tard via "Reinitialiser".
          </p>
          <form className="mt-5 grid gap-4 md:grid-cols-2" onSubmit={handleCreate}>
            <div>
              <label className="mb-2 block text-sm text-slate-200" htmlFor="new_full_name">
                Nom complet
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
                Mot de passe initial
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
                {createMutation.isPending ? "Creation..." : "Creer le compte"}
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
                Annuler
              </Button>
            </div>
          </form>
        </Card>
      ) : null}

      <Card className="p-0">
        <div className="border-b border-white/5 p-5">
          <h3 className="text-lg font-semibold text-white">Comptes provisionnes</h3>
          <p className="mt-1 text-sm text-mutedText">
            {users.length} compte(s) enregistre(s) dans la plateforme.
          </p>
        </div>

        {usersQuery.isLoading ? (
          <div className="p-6 text-sm text-mutedText">Chargement des utilisateurs...</div>
        ) : usersQuery.isError ? (
          <EmptyState
            title="Liste indisponible"
            description="Impossible de recuperer les utilisateurs. Verifie que l'API auth est demarree."
          />
        ) : users.length === 0 ? (
          <EmptyState
            title="Aucun utilisateur"
            description="Cree le premier compte via le bouton 'Nouvel utilisateur'."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead>
                <tr className="border-b border-white/5 text-xs uppercase tracking-[0.18em] text-mutedText">
                  <th className="px-5 py-4">Utilisateur</th>
                  <th className="px-5 py-4">Role</th>
                  <th className="px-5 py-4">Etat</th>
                  <th className="px-5 py-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => {
                  const isSelf = currentUser?.id === user.id;
                  const isAdminRow = user.role === "ADMIN";
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
                          {user.is_active ? "Actif" : "Desactive"}
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
                            title={isAdminRow ? "Le profil admin est protege" : "Modifier"}
                          >
                            <Pencil size={14} />
                            Modifier
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
                            Reinitialiser
                          </Button>
                          <Button
                            type="button"
                            variant="secondary"
                            size="sm"
                            onClick={() => handleToggleActive(user)}
                            disabled={isAdminRow || isSelf}
                            title={
                              isAdminRow
                                ? "Un administrateur ne peut pas etre desactive"
                                : user.is_active
                                  ? "Desactiver le compte"
                                  : "Reactiver le compte"
                            }
                          >
                            <Power size={14} />
                            {user.is_active ? "Desactiver" : "Reactiver"}
                          </Button>
                          <Button
                            type="button"
                            variant="danger"
                            size="sm"
                            onClick={() => handleDelete(user)}
                            disabled={isAdminRow || isSelf}
                            title={
                              isAdminRow
                                ? "Un administrateur ne peut pas etre supprime"
                                : isSelf
                                  ? "Tu ne peux pas supprimer ton propre compte"
                                  : "Supprimer"
                            }
                          >
                            <Trash2 size={14} />
                            Supprimer
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
                <p className="text-xs uppercase tracking-[0.24em] text-mutedText">Modifier</p>
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
                  Nom complet
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
                  {updateMutation.isPending ? "Enregistrement..." : "Enregistrer"}
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => {
                    setEditingUser(null);
                    setEditError(null);
                  }}
                >
                  Annuler
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
                  Reinitialiser le mot de passe
                </p>
                <h3 className="mt-2 text-lg font-semibold text-white">
                  {resetPasswordFor.email}
                </h3>
                <p className="mt-2 text-sm text-mutedText">
                  Le nouveau mot de passe remplace l'actuel. Transmets-le en lieu sur a
                  l'utilisateur.
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
                  Nouveau mot de passe
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
                  {updateMutation.isPending ? "Mise a jour..." : "Valider"}
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => {
                    setResetPasswordFor(null);
                    setResetError(null);
                  }}
                >
                  Annuler
                </Button>
              </div>
            </form>
          </Card>
        </div>
      ) : null}
    </div>
  );
}
