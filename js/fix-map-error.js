// Předpokládaný kód, který pracuje s daty:
function processData(data) {
    // Kontrola, zda data.items existují, pokud ne, použije se prázdné pole
    const items = data?.items || [];
    // Nyní můžeme bezpečně volat .map() na proměnné items
    const result = items.map(item => {
        // Zpracování položky – např. transformace nebo vykreslení
        return processItem(item);
    });
    return result;
}

function processItem(item) {
    // Příklad zpracování položky
    return {
        id: item.id,
        value: item.value
    };
}

// Ukázka použití:
const data = getDataFromSource(); // funkce, která vrací data nebo null
const processed = processData(data);
console.log("Výsledek zpracování:", processed);

// Alternativně můžete vložit kontrolu přímo tam, kde se volá map:
data?.items?.map(item => {
    // Pokud data.items není null, provede se tato funkce.
    console.log("Zpracovávám položku", item);
});