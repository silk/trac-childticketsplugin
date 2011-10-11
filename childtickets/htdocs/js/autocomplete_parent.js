jQuery(document).ready(function($) {
    $("#field-parent").autocomplete(PARENT_AC_PATH, { 
        formatItem: formatParentItem,
        cacheLength: 3, 
        minChars: 1,
        delay: 100,
        max: 20,
    }); 
})

function formatParentItem(row) {
  return row[0] + ": " + row[1]
}

