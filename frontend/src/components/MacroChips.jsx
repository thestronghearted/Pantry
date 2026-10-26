export default function MacroChips({ macros }) {
  if (!macros) return <span className="chip warn">No nutrition data</span>;
  return (
    <>
      <span className="chip"><strong>{macros.kcal}</strong>&nbsp;kcal</span>
      <span className="chip">P {macros.protein}</span>
      <span className="chip">C {macros.carbs}</span>
      <span className="chip">F {macros.fat}</span>
    </>
  );
}
