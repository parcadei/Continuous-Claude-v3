/-
  Proof that addition is commutative for natural numbers.
  We prove: ∀ n m : Nat, n + m = m + n
-/

-- First, we need a helper lemma: n + succ m = succ (n + m)
theorem add_succ (n m : Nat) : n + Nat.succ m = Nat.succ (n + m) := rfl

-- Helper: succ n + m = succ (n + m)
theorem succ_add (n m : Nat) : Nat.succ n + m = Nat.succ (n + m) := by
  induction m with
  | zero => rfl
  | succ m ih =>
    calc Nat.succ n + Nat.succ m
        = Nat.succ (Nat.succ n + m) := rfl
      _ = Nat.succ (Nat.succ (n + m)) := by rw [ih]
      _ = Nat.succ (n + Nat.succ m) := rfl

-- Helper: 0 + n = n (addition is defined by recursion on second arg)
theorem zero_add (n : Nat) : 0 + n = n := by
  induction n with
  | zero => rfl
  | succ n ih =>
    calc 0 + Nat.succ n
        = Nat.succ (0 + n) := rfl
      _ = Nat.succ n := by rw [ih]

-- Main theorem: addition is commutative
theorem add_comm (n m : Nat) : n + m = m + n := by
  induction n with
  | zero =>
    -- Need to show: 0 + m = m + 0
    calc 0 + m = m := zero_add m
      _ = m + 0 := rfl
  | succ n ih =>
    -- Inductive case: succ n + m = m + succ n
    calc Nat.succ n + m
        = Nat.succ (n + m) := succ_add n m
      _ = Nat.succ (m + n) := by rw [ih]
      _ = m + Nat.succ n := rfl

-- Verify it works
#check @add_comm  -- add_comm : ∀ (n m : Nat), n + m = m + n
